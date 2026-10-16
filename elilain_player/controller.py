"""Notified, data-only Qt bridge; library scans never block the UI thread."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Property, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from .playback import AudioPlayer

ASSET_DIR = Path(__file__).parent / "assets"
DARK = dict(bg="#090c19", panel="#d0111b2c", raised="#17263b", border="#456078",
            text="#e5edf8", dim="#aabed7", faint="#849cb8", accent="#7fe9f4", signal="#b6a3fb", error="#ff96b0")
LIGHT = dict(bg="#ecf1f8", panel="#e0f5f8ff", raised="#dfe8f5", border="#a6b7cc",
             text="#192c46", dim="#455a78", faint="#5b6d84", accent="#08637a", signal="#6545a1", error="#a82a50")


def app_directory():
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share")))
    return base / "EliLain-Player"


def clock(milliseconds):
    seconds = max(0, int(milliseconds)) // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


class ScanTask(QThread):
    scanned = Signal(object)
    failed = Signal(str)

    def __init__(self, paths, cache_dir, scanner=None, parent=None):
        super().__init__(parent)
        self.paths, self.cache_dir, self.scanner = paths, cache_dir, scanner

    def run(self):
        try:
            scanner = self.scanner
            if scanner is None:
                from .library import scan_paths
                scanner = scan_paths
            self.scanned.emit(scanner(self.paths, self.cache_dir, self.isInterruptionRequested))
        except Exception as exc:
            self.failed.emit(f"Unable to read this folder: {exc}")


class Controller(QObject):
    libraryChanged = Signal()
    queueChanged = Signal()
    transportChanged = Signal()
    preferencesChanged = Signal()
    uiChanged = Signal()
    safeToClose = Signal()

    def __init__(self, store=None, scan_function=None, parent=None):
        super().__init__(parent)
        if store is None:
            from .library import LibraryStore
            store = LibraryStore(app_directory())
        self.store = store
        self.player = AudioPlayer(self)
        self._scan_factory = scan_function
        self._scan = None
        self._closing = False
        self._cancelled = False
        self._search = ""
        self._view = "library"
        self._status = "Add a music folder. Your files stay exactly where they are."
        self._error = ""
        self._queue_key = None
        self.player.changed.connect(self._playback_changed)
        self.player.failed.connect(self._show_error)
        self.player.set_volume(store.preferences.get("volume", 0.65))
        self.player.shuffle = bool(store.preferences.get("shuffle", False))
        mode = store.preferences.get("repeatMode", "off")
        self.player.repeat_mode = mode if mode in ("off", "all", "one") else "off"

    def _playback_changed(self):
        key = (tuple(t["id"] for t in self.player._queue), self.player.queue_index)
        if key != self._queue_key:
            self._queue_key = key
            self.queueChanged.emit()
        self.transportChanged.emit()

    def _save(self):
        try:
            self.store.save()
        except (OSError, ValueError) as exc:
            self._show_error(f"Unable to save player preferences: {exc}")

    def _show_error(self, text):
        self._error = str(text)
        self.uiChanged.emit()

    def _decorate(self, track):
        data = track.to_dict() if hasattr(track, "to_dict") else dict(track)
        data["coverUrl"] = data.get("coverUrl") or (ASSET_DIR / "lain.png").as_uri()
        data["favorite"] = data.get("id") in self.store.favorites
        return data

    def _visible(self):
        items = self.store.tracks
        if self._view == "favorites":
            items = [t for t in items if t.id in self.store.favorites]
        elif self._view.startswith("playlist:"):
            ids = self.store.playlists.get(self._view[9:], [])
            by_id = {t.id: t for t in items}
            items = [by_id[identity] for identity in ids if identity in by_id]
        if self._search:
            needle = self._search.casefold()
            items = [t for t in items if needle in f"{t.title} {t.artist} {t.album}".casefold()]
        return items

    @Property("QVariantMap", notify=preferencesChanged)
    def palette(self):
        return dict(DARK if self.theme == "dark" else LIGHT)

    @Property(str, notify=preferencesChanged)
    def theme(self):
        return "light" if self.store.preferences.get("theme") == "light" else "dark"

    @Property(str, constant=True)
    def artworkBase(self):
        return ASSET_DIR.as_uri() + "/"

    @Property("QVariantList", notify=libraryChanged)
    def tracks(self):
        return [self._decorate(t) for t in self._visible()]

    @Property(int, notify=libraryChanged)
    def trackCount(self):
        return len(self.store.tracks)

    @Property(str, notify=libraryChanged)
    def activeView(self):
        return self._view

    @Property(str, notify=libraryChanged)
    def viewTitle(self):
        return {"library": "Music library", "favorites": "Favorites"}.get(self._view, self._view[9:])

    @Property(str, notify=libraryChanged)
    def searchText(self):
        return self._search

    @Property("QVariantList", notify=libraryChanged)
    def playlists(self):
        return [dict(name=name, count=len(ids)) for name, ids in self.store.playlists.items()]

    @Property("QVariantList", notify=queueChanged)
    def queue(self):
        return [self._decorate(t) for t in self.player.queue]

    @Property("QVariantMap", notify=queueChanged)
    def currentTrack(self):
        current = self.player.current
        if not current:
            return {}
        found = next((t for t in self.store.tracks if t.id == current.get("id")), current)
        return self._decorate(found)

    queueIndex = Property(int, lambda self: self.player.queue_index, notify=queueChanged)
    playing = Property(bool, lambda self: self.player.playing, notify=transportChanged)
    positionMs = Property(int, lambda self: self.player.position_ms, notify=transportChanged)
    durationMs = Property(int, lambda self: self.player.duration_ms, notify=transportChanged)
    positionText = Property(str, lambda self: clock(self.player.position_ms), notify=transportChanged)
    durationText = Property(str, lambda self: clock(self.player.duration_ms), notify=transportChanged)
    seekable = Property(bool, lambda self: self.player.seekable, notify=transportChanged)
    volume = Property(float, lambda self: self.player.volume, notify=transportChanged)
    muted = Property(bool, lambda self: self.player.muted, notify=transportChanged)
    shuffle = Property(bool, lambda self: self.player.shuffle, notify=transportChanged)
    repeatMode = Property(str, lambda self: self.player.repeat_mode, notify=transportChanged)
    levels = Property("QVariantList", lambda self: self.player.levels, notify=transportChanged)
    scanBusy = Property(bool, lambda self: self._scan is not None, notify=uiChanged)
    statusText = Property(str, lambda self: self._status, notify=uiChanged)
    errorText = Property(str, lambda self: self._error, notify=uiChanged)
    motionEnabled = Property(bool, lambda self: bool(self.store.preferences.get("motionEnabled", False)),
                             notify=preferencesChanged)

    @Slot(str)
    def setSearch(self, text):
        self._search = text.strip()
        self.libraryChanged.emit()

    @Slot(str)
    def selectView(self, view):
        if view in ("library", "favorites") or (view.startswith("playlist:") and view[9:] in self.store.playlists):
            self._view = view
            self.libraryChanged.emit()

    @Slot(str)
    def playTrack(self, identity):
        # Search may change visible rows; the running queue remains an independent snapshot.
        visible = [self._decorate(t) for t in self._visible()]
        if identity not in {t["id"] for t in visible}:
            visible = [self._decorate(t) for t in self.store.tracks]
        if identity not in {t["id"] for t in visible}:
            self._show_error("This track is no longer in the library. Add its folder again.")
            return
        if self.player.set_queue(visible, identity):
            self._error = ""
            self._status = "Local playback. Nothing leaves this machine."
            self.uiChanged.emit()

    @Slot(int)
    def playQueued(self, index):
        self.player._play_index(index)

    @Slot()
    def togglePlayback(self):
        if not self.player.current and self.tracks:
            self.playTrack(self.tracks[0]["id"])
        else:
            self.player.toggle()

    @Slot()
    def nextTrack(self):
        self.player.next()

    @Slot()
    def previousTrack(self):
        self.player.previous()

    @Slot(int)
    def seek(self, value):
        self.player.seek(value)

    @Slot(float)
    def setVolume(self, value):
        self.player.set_volume(value)
        self.store.preferences["volume"] = self.player.volume
        self._save()

    @Slot()
    def toggleMute(self):
        self.player.toggle_mute()

    @Slot()
    def toggleShuffle(self):
        self.player.toggle_shuffle()
        self.store.preferences["shuffle"] = self.player.shuffle
        self._save()

    @Slot()
    def cycleRepeat(self):
        self.player.cycle_repeat()
        self.store.preferences["repeatMode"] = self.player.repeat_mode
        self._save()

    @Slot(str)
    def toggleFavorite(self, identity):
        if identity in {t.id for t in self.store.tracks}:
            self.store.toggle_favorite(identity)
            self.libraryChanged.emit()
            self.queueChanged.emit()

    @Slot(str, result=bool)
    def createPlaylist(self, name):
        name = name.strip()
        if not self.store.create_playlist(name):
            self._show_error("Choose a new, nonempty playlist name (up to 80 characters).")
            return False
        self.libraryChanged.emit()
        return True

    @Slot(str, str, result=bool)
    def addToPlaylist(self, name, identity):
        result = self.store.add_to_playlist(name, identity)
        if result:
            self.libraryChanged.emit()
        return result

    @Slot(str, result=bool)
    def removeFromLibrary(self, identity):
        result = self.store.remove_from_library(identity)
        if result:
            self._status = "Removed from the library only. The audio file was not deleted."
            self.libraryChanged.emit()
            self.queueChanged.emit()
            self.uiChanged.emit()
        return result

    @Slot()
    def toggleTheme(self):
        self.store.preferences["theme"] = "light" if self.theme == "dark" else "dark"
        self._save()
        self.preferencesChanged.emit()

    @Slot(bool)
    def setMotion(self, value):
        self.store.preferences["motionEnabled"] = bool(value)
        self._save()
        self.preferencesChanged.emit()

    @Slot()
    def clearError(self):
        self._error = ""
        self.uiChanged.emit()

    @Slot()
    def revealCurrent(self):
        if not self.player.current:
            return
        path = Path(self.player.current["path"])
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", "/select,", str(path)], close_fds=True)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    @Slot(QUrl)
    def addFolder(self, url):
        self._begin_scan([url.toLocalFile()] if url.isLocalFile() else [])

    @Slot("QVariantList")
    def addFiles(self, urls):
        paths = []
        for value in urls:
            url = value if isinstance(value, QUrl) else QUrl(str(value))
            if url.isLocalFile():
                paths.append(url.toLocalFile())
        self._begin_scan(paths)

    def _begin_scan(self, paths):
        if self._scan is not None or self._closing:
            self._show_error("Wait for the current scan, or stop it before adding another folder.")
            return
        if not paths:
            self._show_error("Choose local audio files or a music folder, not an internet link.")
            return
        self._cancelled = False
        self._error = ""
        self._status = "Reading local metadata… You can keep listening while the library updates."
        cache_dir = getattr(self.store, "directory", app_directory()) / "artwork"
        self._scan = ScanTask(paths, cache_dir, self._scan_factory, self)
        self._scan.scanned.connect(self._scanned)
        self._scan.failed.connect(self._show_error)
        self._scan.finished.connect(self._scan_finished)
        self._scan.start()
        self.uiChanged.emit()

    def _scanned(self, result):
        try:
            count = self.store.merge(result)
            self._status = f"Added {count} track{'s' if count != 1 else ''}. Audio files were not moved or changed."
            if self._cancelled:
                self._status = "Scan stopped. Tracks already read are kept in the library."
            if result.errors:
                self._error = "Some files could not be read. " + "; ".join(result.errors[:3])
            self.libraryChanged.emit()
            self.queueChanged.emit()
        except (OSError, ValueError) as exc:
            self._show_error(f"Unable to save the updated library: {exc}")
        self.uiChanged.emit()

    def _scan_finished(self):
        worker = self._scan
        self._scan = None
        if worker:
            worker.deleteLater()
        self.uiChanged.emit()
        if self._closing:
            self._save()
            self.safeToClose.emit()

    @Slot()
    def cancelScan(self):
        if self._scan is not None:
            self._cancelled = True
            self._scan.requestInterruption()
            self._status = "Stopping the scan…"
            self.uiChanged.emit()

    @Slot(result=bool)
    def requestClose(self):
        self._closing = True
        self.player.shutdown()
        if self._scan is not None:
            self.cancelScan()
            return False
        self._save()
        return True
