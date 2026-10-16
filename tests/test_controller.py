from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from conftest import until
from PySide6.QtCore import QUrl


@dataclass
class FixtureTrack:
    id: str
    path: str
    title: str
    artist: str = "Fixture artist"
    album: str = "Acceptance fixtures"

    def to_dict(self):
        return {**vars(self), "durationMs": 6000, "durationText": "0:06", "format": "WAV",
                "bitrate": 256000, "sampleRate": 16000, "coverUrl": "", "url": Path(self.path).as_uri()}


class FixtureStore:
    """Explicit test-only data store; playback still uses real Qt audio."""
    def __init__(self, path):
        self.directory = path
        self.tracks = []
        self.roots = []
        self.favorites = set()
        self.playlists = {}
        self.preferences = {}
        self.saves = 0

    def save(self):
        self.saves += 1

    def merge(self, result):
        old = {t.id for t in self.tracks}
        self.tracks.extend(t for t in result.tracks if t.id not in old)
        self.save()
        return len(self.tracks) - len(old)

    def toggle_favorite(self, identity):
        if identity in self.favorites:
            self.favorites.remove(identity)
        else:
            self.favorites.add(identity)
        self.save()
        return identity in self.favorites

    def create_playlist(self, name):
        if not name.strip() or name in self.playlists:
            return False
        self.playlists[name] = []
        self.save()
        return True

    def add_to_playlist(self, name, identity):
        if name not in self.playlists or identity not in {t.id for t in self.tracks}:
            return False
        if identity not in self.playlists[name]:
            self.playlists[name].append(identity)
        self.save()
        return True

    def remove_from_library(self, identity):
        self.tracks = [t for t in self.tracks if t.id != identity]
        self.save()
        return True


def test_real_bridge_search_does_not_mutate_playback_queue(qapp, tmp_path, audio_file):
    from elilain_player.controller import Controller
    store = FixtureStore(tmp_path)
    store.tracks = [FixtureTrack("a", str(audio_file), "Alpha"), FixtureTrack("b", str(audio_file), "Beta")]
    backend = Controller(store=store)
    backend.setVolume(0)
    try:
        backend.playTrack("a")
        until(lambda: backend.durationMs > 0)
        backend.setSearch("Beta")
        assert [t["id"] for t in backend.tracks] == ["b"]
        assert [t["id"] for t in backend.queue] == ["a", "b"]
        assert backend.currentTrack["id"] == "a"
        backend.playQueued(1)
        assert backend.currentTrack["id"] == "b"
        assert [t["id"] for t in backend.queue] == ["a", "b"]
        backend.playQueued(0)
        backend.toggleFavorite("a")
        backend.setSearch("")
        backend.selectView("favorites")
        assert [t["id"] for t in backend.tracks] == ["a"]
        assert backend.currentTrack["favorite"]
        assert backend.createPlaylist("Night walks")
        assert backend.addToPlaylist("Night walks", "b")
        backend.selectView("playlist:Night walks")
        assert [t["id"] for t in backend.tracks] == ["b"]
        assert backend.removeFromLibrary("b")
        assert audio_file.exists(), "Library removal must never delete music"
        assert backend.requestClose()
    finally:
        backend.player.shutdown()


def test_import_actual_qthread_and_deferred_close(qapp, tmp_path, audio_file):
    import threading
    from elilain_player.controller import Controller
    release = threading.Event()
    entered = threading.Event()
    cancelled = threading.Event()
    store = FixtureStore(tmp_path)

    def scanner(paths, cache_dir, is_cancelled):
        entered.set()
        for _ in range(100):
            if is_cancelled():
                cancelled.set()
                break
            if release.wait(0.01):
                break
        return SimpleNamespace(tracks=[], roots=[], errors=[])

    backend = Controller(store=store, scan_function=scanner)
    closed = []
    backend.safeToClose.connect(lambda: closed.append(True))
    backend.addFolder(QUrl.fromLocalFile(str(tmp_path)))
    try:
        until(entered.is_set)
        assert backend.scanBusy
        worker = backend._scan
        assert not backend.requestClose()
        assert backend._scan is worker, "Retain QThread until finished"
        until(lambda: bool(closed))
        assert cancelled.is_set()
        assert not backend.scanBusy and backend._scan is None
    finally:
        release.set()
        if backend._scan is not None:
            backend._scan.wait(2000)
        backend.player.shutdown()
