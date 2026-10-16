"""Real local fixtures only: never read or modify a user's music collection."""
from dataclasses import FrozenInstanceError
import importlib
import importlib.util
from pathlib import Path
import os
import wave

import pytest


def library():
    assert importlib.util.find_spec("elilain_player.library") is not None, "pure library module is missing"
    return importlib.import_module("elilain_player.library")


def make_wav(path, seconds=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * (8000 * seconds))
    return path


def test_track_is_frozen_and_exports_plain_local_map(tmp_path):
    mod = library()
    path = tmp_path / "space & 日本.wav"
    track = mod.Track("id", str(path), "title", "artist", "album", 65009, "WAV", 128000, 8000, "")
    assert track.to_dict() == {
        "id": "id", "path": str(path), "title": "title", "artist": "artist", "album": "album",
        "durationMs": 65009, "format": "WAV", "bitrate": 128000, "sampleRate": 8000,
        "coverUrl": "", "url": path.as_uri(), "durationText": "1:05",
    }
    with pytest.raises(FrozenInstanceError):
        track.title = "changed"


def test_recursive_scan_deduplicates_valid_audio_and_reports_corruption(tmp_path):
    mod = library()
    root = tmp_path / "music"
    audio = make_wav(root / "nested" / "Artist - Title.WAV")
    original = audio.read_bytes()
    (root / "broken.mp3").write_bytes(b"not audio")
    (root / "empty.flac").touch()
    (root / "notes.txt").write_text("ignore")
    result = mod.scan_paths([root, audio, root / "nested" / ".."], tmp_path / "cache")
    assert len(result.tracks) == 1
    track = result.tracks[0]
    assert track.path == str(audio.resolve())
    assert track.title == "Artist - Title"  # no lossy filename guessing
    assert track.artist == "Unknown Artist"
    assert track.album == "Unknown Album"
    assert track.durationMs == 1000
    assert track.sampleRate == 8000
    assert track.format == "WAV"
    assert track.coverUrl == ""
    assert len(result.errors) == 2
    assert any("broken.mp3" in error for error in result.errors)
    assert any("empty.flac" in error for error in result.errors)
    assert str(root.resolve()) in result.roots
    assert audio.read_bytes() == original
    assert not (root / "nested" / "cache").exists()
    again = mod.scan_paths([audio], tmp_path / "cache")
    assert again.tracks[0].id == track.id


def test_reads_real_id3_metadata_without_modifying_source(tmp_path):
    from mutagen.wave import WAVE
    from mutagen.id3 import TIT2, TPE1, TALB

    mod = library()
    path = make_wav(tmp_path / "fallback.wav")
    tagged = WAVE(path)
    tagged.add_tags()
    tagged.tags.add(TIT2(encoding=3, text="  Wired\x00\n Signal  "))
    tagged.tags.add(TPE1(encoding=3, text="Bôa"))
    tagged.tags.add(TALB(encoding=3, text="Twilight"))
    tagged.save()
    before = path.read_bytes()
    result = mod.scan_paths([path], tmp_path / "cache")
    assert not result.errors
    assert result.tracks[0].title == "Wired Signal"
    assert result.tracks[0].artist == "Bôa"
    assert result.tracks[0].album == "Twilight"
    assert path.read_bytes() == before


def test_cached_store_merge_is_persistent_idempotent_and_never_rescans(tmp_path, monkeypatch):
    mod = library()
    source = make_wav(tmp_path / "music" / "one.wav")
    scan = mod.scan_paths([source.parent], tmp_path / "cache")
    assert hasattr(mod, "LibraryStore"), "persistent library store is missing"
    store = mod.LibraryStore(tmp_path / "state")
    assert store.tracks == []
    assert store.favorites == set()
    assert store.playlists == {}
    assert store.preferences == {"theme": "dark", "volume": 0.65, "shuffle": False,
                                 "repeatMode": "off", "motionEnabled": False}
    assert store.merge(scan) == 1
    assert store.merge(scan) == 0
    store.preferences["theme"] = "light"
    store.preferences["volume"] = 0.4
    store.save()
    source.unlink()  # missing media must not invalidate cached state
    monkeypatch.setattr(mod.mutagen, "File", lambda *a, **k: pytest.fail("startup reparsed media"))
    loaded = mod.LibraryStore(tmp_path / "state")
    assert loaded.tracks == store.tracks
    assert loaded.roots == [str(source.parent.resolve())]
    assert loaded.preferences["theme"] == "light"
    assert loaded.preferences["volume"] == 0.4
    assert (tmp_path / "state" / "library.json").is_file()
    assert list((tmp_path / "state").glob("*.tmp")) == []


def test_favorites_use_stable_ids_and_persist_across_metadata_refresh(tmp_path):
    from dataclasses import replace

    mod = library()
    scan = mod.scan_paths([make_wav(tmp_path / "one.wav"), make_wav(tmp_path / "two.wav")], tmp_path / "cache")
    store = mod.LibraryStore(tmp_path / "state")
    store.merge(scan)
    wanted = scan.tracks[1].id
    assert hasattr(store, "toggle_favorite"), "favorite operations are missing"
    assert store.toggle_favorite("missing") is False
    assert store.favorites == set()
    assert store.toggle_favorite(wanted) is True
    refresh = mod.ScanResult([replace(scan.tracks[1], title="new title"), scan.tracks[0]], [], [])
    assert store.merge(refresh) == 0
    loaded = mod.LibraryStore(tmp_path / "state")
    assert loaded.favorites == {wanted}
    assert loaded.toggle_favorite(wanted) is False
    assert mod.LibraryStore(tmp_path / "state").favorites == set()


def test_playlists_validate_names_and_persist_unique_ordered_ids(tmp_path):
    mod = library()
    scan = mod.scan_paths([make_wav(tmp_path / "one.wav"), make_wav(tmp_path / "two.wav")], tmp_path / "cache")
    store = mod.LibraryStore(tmp_path / "state")
    store.merge(scan)
    assert hasattr(store, "create_playlist"), "playlist operations are missing"
    assert store.create_playlist("  Wired  ") is True
    for name in ("", " \n ", "x" * 81, "Wired", "wired", "bad\x00name"):
        assert store.create_playlist(name) is False
    first, second = [track.id for track in scan.tracks]
    assert store.add_to_playlist("absent", first) is False
    assert store.add_to_playlist("Wired", "absent") is False
    assert store.add_to_playlist("Wired", second) is True
    assert store.add_to_playlist("Wired", first) is True
    assert store.add_to_playlist("Wired", second) is False
    store.merge(mod.ScanResult(list(reversed(scan.tracks)), [], []))
    assert mod.LibraryStore(tmp_path / "state").playlists == {"Wired": [second, first]}


def test_removal_only_removes_library_references_and_never_source_files(tmp_path):
    mod = library()
    source = make_wav(tmp_path / "one.wav")
    original = source.read_bytes()
    scan = mod.scan_paths([source], tmp_path / "cache")
    store = mod.LibraryStore(tmp_path / "state")
    store.merge(scan)
    id = scan.tracks[0].id
    store.toggle_favorite(id)
    store.create_playlist("Wired")
    store.add_to_playlist("Wired", id)
    assert hasattr(store, "remove_from_library"), "non-destructive removal is missing"
    assert store.remove_from_library("missing") is False
    assert store.remove_from_library(id) is True
    assert source.read_bytes() == original
    loaded = mod.LibraryStore(tmp_path / "state")
    assert loaded.tracks == []
    assert loaded.favorites == set()
    assert loaded.playlists == {"Wired": []}
    assert loaded.remove_from_library(id) is False
    assert loaded.merge(scan) == 1
    assert loaded.tracks[0].id == id


@pytest.mark.parametrize("raw", ["{broken", "null", "[]", '"text"', '{"tracks": 3}',
                                      '{"roots": null, "favorites": {}, "playlists": [], "preferences": []}',
                                      "\ufeff{}", "\ud800"])
def test_invalid_json_or_shapes_are_recoverable_without_overwriting_on_load(tmp_path, raw):
    mod = library()
    state = tmp_path / "state"
    state.mkdir()
    path = state / "library.json"
    original = raw.encode("utf-8", errors="surrogatepass")
    path.write_bytes(original)
    store = mod.LibraryStore(state)
    assert store.tracks == []
    assert store.roots == []
    assert store.favorites == set()
    assert store.playlists == {}
    assert store.preferences == mod.DEFAULT_PREFERENCES
    assert path.read_bytes() == original
    store.save()
    assert mod.LibraryStore(state).tracks == []


def test_state_recovers_valid_rows_and_filters_bad_references_and_preferences(tmp_path):
    import json
    from dataclasses import asdict

    mod = library()
    scan = mod.scan_paths([make_wav(tmp_path / "one.wav")], tmp_path / "cache")
    row = asdict(scan.tracks[0])
    state = tmp_path / "state"
    state.mkdir()
    data = {"tracks": [None, {}, dict(row, durationMs="bad"), row, row],
            "roots": [str(tmp_path), 12, str(tmp_path)],
            "favorites": [row["id"], "missing", [], row["id"]],
            "playlists": {"Wired": [row["id"], "missing", {}, row["id"]], "": [], "bad": 3},
            "preferences": {"theme": "hacked", "volume": 4, "shuffle": "false",
                            "repeatMode": "invalid", "motionEnabled": True}}
    (state / "library.json").write_text(json.dumps(data), encoding="utf-8")
    store = mod.LibraryStore(state)
    assert store.tracks == scan.tracks
    assert store.roots == [str(tmp_path)]
    assert store.favorites == {row["id"]}
    assert store.playlists == {"Wired": [row["id"]]}
    assert store.preferences == {"theme": "dark", "volume": 1.0, "shuffle": False,
                                 "repeatMode": "off", "motionEnabled": True}


def image_bytes(size=(1600, 900), color="red"):
    from PIL import Image
    from io import BytesIO

    stream = BytesIO()
    Image.new("RGB", size, color).save(stream, format="PNG")
    return stream.getvalue()


def local_url_path(url):
    from urllib.parse import unquote, urlparse
    from urllib.request import url2pathname

    return Path(url2pathname(unquote(urlparse(url).path)))


def test_real_embedded_art_is_bounded_content_addressed_and_read_only(tmp_path):
    from mutagen.wave import WAVE
    from mutagen.id3 import APIC
    from PIL import Image

    mod = library()
    source = make_wav(tmp_path / "music" / "tagged.wav")
    tags = WAVE(source)
    tags.add_tags()
    tags.tags.add(APIC(encoding=3, mime="image/png", type=3, desc="../../escape", data=image_bytes()))
    tags.save()
    original = source.read_bytes()
    cache = tmp_path / "cache"
    result = mod.scan_paths([source], cache)
    assert not result.errors
    assert result.tracks[0].coverUrl, "embedded artwork was not cached"
    cover = local_url_path(result.tracks[0].coverUrl)
    assert cover.is_relative_to(cache.resolve())
    assert cover.is_file()
    assert cover.stat().st_size < 2 * 1024 * 1024
    with Image.open(cover) as image:
        assert max(image.size) <= 1024
        assert image.getpixel((10, 10))[0] > 200
    before_mtime = cover.stat().st_mtime_ns
    again = mod.scan_paths([source], cache)
    assert again.tracks[0].coverUrl == result.tracks[0].coverUrl
    assert cover.stat().st_mtime_ns == before_mtime
    assert source.read_bytes() == original
    assert not (tmp_path / "escape").exists()


@pytest.mark.parametrize("name", ["cover.jpg", "Folder.PNG", "front.jpeg", "one.png"])
def test_sidecar_art_is_local_cached_and_source_preserved(tmp_path, name):
    mod = library()
    source = make_wav(tmp_path / "music" / "one.wav")
    sidecar = source.parent / name
    original = image_bytes((80, 80), "blue")
    sidecar.write_bytes(original)
    result = mod.scan_paths([source], tmp_path / "cache")
    assert not result.errors
    assert result.tracks[0].coverUrl, "sidecar artwork was not cached"
    cover = local_url_path(result.tracks[0].coverUrl)
    assert cover.parent == (tmp_path / "cache").resolve()
    assert cover.is_file()
    assert sidecar.read_bytes() == original


@pytest.mark.parametrize("kind", ["bytes", "pixels", "corrupt", "cache_unwritable"])
def test_bad_or_oversize_art_never_drops_valid_audio(tmp_path, monkeypatch, kind):
    mod = library()
    source = make_wav(tmp_path / "music" / "one.wav")
    sidecar = source.parent / "cover.png"
    cache = tmp_path / "cache"
    if kind == "bytes":
        monkeypatch.setattr(mod, "MAX_ART_BYTES", 64)
        sidecar.write_bytes(image_bytes())
    elif kind == "pixels":
        monkeypatch.setattr(mod, "MAX_ART_PIXELS", 20)
        sidecar.write_bytes(image_bytes((10, 10)))
    elif kind == "corrupt":
        sidecar.write_bytes(b"not an image")
    else:
        sidecar.write_bytes(image_bytes((10, 10)))
        cache.write_text("not a directory")
    result = mod.scan_paths([source], cache)
    assert len(result.tracks) == 1
    assert result.tracks[0].coverUrl == ""
    assert result.errors, "artwork failure must be recoverably reported"
    assert source.is_file()
    assert not list(tmp_path.rglob("*.tmp"))


def transcode_fixture(tmp_path, extension):
    import shutil
    import subprocess

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("optional ffmpeg fixture encoder is unavailable")
    source = make_wav(tmp_path / "input.wav")
    target = tmp_path / ("encoded." + extension)
    options = {
        "mp3": ["-c:a", "libmp3lame"], "flac": ["-c:a", "flac"],
        "ogg": ["-c:a", "libvorbis"], "opus": ["-c:a", "libopus", "-ar", "48000"],
        "m4a": ["-c:a", "aac"], "aac": ["-c:a", "aac", "-f", "adts"],
        "wma": ["-c:a", "wmav2", "-ar", "44100"], "aiff": ["-c:a", "pcm_s16be"],
        "alac": ["-c:a", "alac", "-f", "ipod"],
    }
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(source),
                    *options[extension], "-metadata", "title=Real Fixture", "-metadata", "artist=Local Artist",
                    "-metadata", "album=Local Album", str(target)], check=True, capture_output=True, timeout=30)
    return target


@pytest.mark.parametrize("extension", ["mp3", "flac", "ogg", "opus", "m4a", "aac", "wma", "aiff", "alac"])
def test_actual_supported_formats_are_readable(tmp_path, extension):
    mod = library()
    source = transcode_fixture(tmp_path, extension)
    original = source.read_bytes()
    result = mod.scan_paths([source], tmp_path / "cache")
    assert not result.errors
    assert len(result.tracks) == 1
    track = result.tracks[0]
    assert 800 <= track.durationMs <= 2000
    assert track.sampleRate > 0
    assert track.format == extension.upper()
    if extension not in {"aac", "aiff"}:
        assert track.title == "Real Fixture"
        assert track.artist == "Local Artist"
        assert track.album == "Local Album"
    assert source.read_bytes() == original


@pytest.mark.parametrize("extension", ["flac", "m4a", "ogg", "opus"])
def test_real_non_id3_embedded_art_is_cached(tmp_path, extension):
    import base64
    import mutagen
    from mutagen.flac import Picture
    from mutagen.mp4 import MP4Cover

    mod = library()
    source = transcode_fixture(tmp_path, extension)
    tags = mutagen.File(source)
    data = image_bytes((50, 50))
    if extension == "m4a":
        tags["covr"] = [MP4Cover(data, imageformat=MP4Cover.FORMAT_PNG)]
    else:
        picture = Picture()
        picture.type = 3
        picture.mime = "image/png"
        picture.data = data
        if extension == "flac":
            tags.add_picture(picture)
        else:
            tags["metadata_block_picture"] = [base64.b64encode(picture.write()).decode("ascii")]
    tags.save()
    before = source.read_bytes()
    result = mod.scan_paths([source], tmp_path / "cache")
    assert not result.errors
    assert len(result.tracks) == 1
    assert result.tracks[0].coverUrl, f"{extension} embedded artwork is missing"
    assert local_url_path(result.tracks[0].coverUrl).is_file()
    assert source.read_bytes() == before


def make_directory_link(link: Path, target: Path) -> bool:
    """Windows junctions and POSIX symlinks both exercise link-loop handling."""
    import subprocess

    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                                capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True
    try:
        link.symlink_to(target, target_is_directory=True)
        return True
    except OSError:
        return False


def test_recursive_scan_survives_directory_link_loops(tmp_path):
    mod = library()
    root = tmp_path / "music"
    audio = make_wav(root / "one.wav")
    if not make_directory_link(root / "loop", root):
        pytest.skip("directory links need extra privileges in this environment")
    result = mod.scan_paths([root], tmp_path / "cache")
    assert [track.path for track in result.tracks] == [str(audio.resolve())]


def test_cancellation_stops_early_without_partial_writes(tmp_path):
    mod = library()
    root = tmp_path / "music"
    for index in range(6):
        make_wav(root / f"{index:02d}.wav")
    cancelled = {"value": False}
    result = mod.scan_paths([root], tmp_path / "cache", lambda: cancelled["value"])
    assert len(result.tracks) == 6
    assert result.errors == []
    state = {"seen": 0}
    real_file = mod.mutagen.File

    def counting_file(*args, **kwargs):
        state["seen"] += 1
        return real_file(*args, **kwargs)

    monkey = pytest.MonkeyPatch()
    monkey.setattr(mod.mutagen, "File", counting_file)
    try:
        partial = mod.scan_paths([root], tmp_path / "cache", lambda: state["seen"] >= 3)
    finally:
        monkey.undo()
    assert 0 < len(partial.tracks) < 6
    assert state["seen"] < 6
    assert not list(tmp_path.rglob("*.tmp"))


def test_scan_reports_missing_sources_and_repeated_scans_are_stable(tmp_path):
    mod = library()
    first = make_wav(tmp_path / "music" / "one.wav")
    second = make_wav(tmp_path / "music" / "two.wav")
    one = mod.scan_paths([tmp_path / "music", tmp_path / "gone"], tmp_path / "cache")
    two = mod.scan_paths([tmp_path / "music", tmp_path / "gone"], tmp_path / "cache")
    assert one.tracks == two.tracks
    assert [t.id for t in one.tracks] == [t.id for t in two.tracks]
    assert one.roots == two.roots == [str((tmp_path / "music").resolve())]
    assert len(one.errors) == 1 and "gone" in one.errors[0]
    assert first.is_file() and second.is_file()


def test_failed_atomic_save_keeps_previous_state_and_leaves_no_temp(tmp_path):
    mod = library()
    state = tmp_path / "state"
    store = mod.LibraryStore(state)
    store.tracks = [mod.Track("id", str(tmp_path / "a.wav"), "t", "ar", "al", 1000, "WAV", 0, 0, "")]
    store.save()
    store.create_playlist("Wired")
    good = (state / "library.json").read_text(encoding="utf-8")
    assert mod.LibraryStore(state).playlists == {"Wired": []}
    store.playlists["Wired"].append("ghost")

    def explode(*args, **kwargs):
        raise OSError("disk full")

    monkey = pytest.MonkeyPatch()
    monkey.setattr(mod.os, "replace", explode)
    try:
        with pytest.raises(OSError):
            store.save()
    finally:
        monkey.undo()
    assert (state / "library.json").read_text(encoding="utf-8") == good
    assert not list(state.glob("*.tmp"))
    assert mod.LibraryStore(state).playlists == {"Wired": []}
    store.save()
    assert mod.LibraryStore(state).playlists == {"Wired": []}


def test_few_thousand_tracks_round_trip_through_state_json(tmp_path):
    import time

    mod = library()
    store = mod.LibraryStore(tmp_path / "state")
    tracks = [mod.Track(f"id{index:05d}", str(tmp_path / f"{index:05d}.wav"), f"Title {index}",
                        "Artist", "Album", 180000 + index, "MP3", 320000, 44100, "")
              for index in range(3000)]
    store.merge(mod.ScanResult(tracks, [str(tmp_path)], []))
    store.create_playlist("Wired")
    for track in tracks[::50]:
        store.add_to_playlist("Wired", track.id)
    store.toggle_favorite(tracks[7].id)
    start = time.perf_counter()
    loaded = mod.LibraryStore(tmp_path / "state")
    elapsed = time.perf_counter() - start
    assert len(loaded.tracks) == 3000
    assert loaded.playlists["Wired"] == [t.id for t in tracks[::50]]
    assert loaded.favorites == {tracks[7].id}
    assert elapsed < 2.0, f"cached startup took {elapsed:.2f}s"
