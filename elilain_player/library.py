"""Offline, read-only audio indexing and application-owned state persistence."""
from dataclasses import asdict, dataclass
from pathlib import Path
from collections.abc import Callable
import hashlib
import math
import os
import unicodedata
import json
import tempfile
from io import BytesIO
import warnings
import base64
from types import SimpleNamespace

from mutagen.flac import Picture, error as FlacError

from PIL import Image, ImageOps, UnidentifiedImageError

import mutagen

SUPPORTED_EXTENSIONS = frozenset({".mp3", ".flac", ".wav", ".ogg", ".opus", ".m4a", ".aac", ".wma", ".aiff", ".alac"})


@dataclass(frozen=True)
class Track:
    id: str
    path: str
    title: str
    artist: str
    album: str
    durationMs: int
    format: str
    bitrate: int
    sampleRate: int
    coverUrl: str

    def to_dict(self) -> dict:
        result = asdict(self)
        result["url"] = Path(self.path).absolute().as_uri()
        seconds = max(0, self.durationMs) // 1000
        result["durationText"] = f"{seconds // 60}:{seconds % 60:02d}"
        return result


@dataclass
class ScanResult:
    tracks: list[Track]
    roots: list[str]
    errors: list[str]


def _canonical(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def _text(value, fallback: str = "") -> str:
    if hasattr(value, "text"):
        value = value.text
    if isinstance(value, (bytes, bytearray)):
        value = bytes(value).decode("utf-8", "ignore")
    if isinstance(value, (list, tuple)):
        parts = [_text(item) for item in value[:8]]
        unique = list(dict.fromkeys(parts))
        if not unique:
            return fallback
        value = " ".join(unique)
    if value is None:
        return fallback
    if not isinstance(value, str):
        try:
            value = str(value)
        except (TypeError, ValueError):
            return fallback
    value = "".join(" " if unicodedata.category(c).startswith("C") else c for c in value[:4096])
    return " ".join(value.split())[:1024] or fallback


def _tag(audio, keys, fallback):
    tags = getattr(audio, "tags", None)
    if tags is None or not hasattr(tags, "get"):
        return fallback
    for key in keys:
        value = _text(tags.get(key))
        if value:
            return value
    return fallback


def _frames(tags, key):
    """mutagen tag mappings differ: ID3/ASF use get, MP4 and Vorbis use subscripting."""
    if tags is None:
        return []
    try:
        if hasattr(tags, "get"):
            value = tags.get(key)
        elif key in tags:
            value = tags[key]
        else:
            value = None
    except (KeyError, TypeError, ValueError):
        return []
    return [value for value in ([*value] if isinstance(value, (list, tuple)) else [value]) if value is not None]


def _frame_bytes(frame) -> bytes:
    """MP4TagCover subclasses bytes, so both bytes values and .data objects appear."""
    data = getattr(frame, "data", frame)
    if isinstance(data, (bytes, bytearray)) and data:
        return bytes(data)
    return b""


MAX_ART_BYTES = 8 * 1024 * 1024
MAX_ART_PIXELS = 16_000_000
MAX_ART_EDGE = 1024


def _cache_image(data: bytes, cache_dir: Path) -> str:
    if len(data) > MAX_ART_BYTES:
        raise ValueError("artwork exceeds byte limit")
    if not data:
        return ""
    cache_dir = Path(cache_dir).resolve()
    target = cache_dir / (hashlib.sha256(data).hexdigest() + ".jpg")
    if target.is_symlink():
        raise ValueError("unsafe artwork cache symlink")
    if target.is_file() and 0 < target.stat().st_size <= MAX_ART_BYTES:
        return target.as_uri()
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(BytesIO(data)) as original:
            if original.width * original.height > MAX_ART_PIXELS:
                raise ValueError("artwork exceeds pixel limit")
            original.thumbnail((MAX_ART_EDGE, MAX_ART_EDGE))
            image = ImageOps.exif_transpose(original).convert("RGB")
            encoded = BytesIO()
            image.save(encoded, format="JPEG", quality=88)
            payload = encoded.getvalue()
    if len(payload) > MAX_ART_BYTES:
        raise ValueError("encoded artwork exceeds byte limit")
    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=cache_dir, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return target.as_uri()


FIXED_SAMPLE_RATES = {"opus": 48000}


def _sample_rate(audio, path: Path) -> int:
    rate = int(getattr(audio.info, "sample_rate", 0) or 0)
    if rate > 0:
        return rate
    return FIXED_SAMPLE_RATES.get(path.suffix.lower()[1:], 0)


def _cover(audio, path: Path, cache_dir: Path, errors: list[str]) -> str:
    tags = getattr(audio, "tags", None)
    frames = []
    if hasattr(tags, "getall"):
        try:
            frames += list(tags.getall("APIC"))
        except (KeyError, ValueError, AttributeError) as exc:
            errors.append(f"{path}: artwork: {exc}")
    for cover in _frames(tags, "covr"):
        data = _frame_bytes(cover)
        if data:
            frames.append(SimpleNamespace(type=3, data=data))
    for value in _frames(tags, "metadata_block_picture"):
        try:
            frames.append(Picture(base64.b64decode(_text(value))))
        except (ValueError, TypeError, FlacError) as exc:
            errors.append(f"{path}: artwork: {exc}")
    frames += [picture for picture in getattr(audio, "pictures", []) if isinstance(picture.data, bytes)]
    frames.sort(key=lambda frame: getattr(frame, "type", 3) != 3)
    for frame in frames:
        try:
            url = _cache_image(frame.data, cache_dir)
            if url:
                return url
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            errors.append(f"{path}: artwork: {exc}")
    for stem in (path.stem, "cover", "folder", "front"):
        for extension in (".jpg", ".jpeg", ".png", ".webp"):
            candidate = path.parent / (stem + extension)
            try:
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                with candidate.open("rb") as stream:
                    data = stream.read(MAX_ART_BYTES + 1)
                url = _cache_image(data, cache_dir)
                if url:
                    return url
            except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
                errors.append(f"{candidate}: artwork: {exc}")
    return ""


def scan_paths(paths, cache_dir: Path, cancelled: Callable[[], bool] = lambda: False) -> ScanResult:
    """Read local sources only. IDs identify canonical paths, never row positions."""
    result = ScanResult([], [], [])
    seen: set[str] = set()

    def inspect(path: Path):
        if cancelled() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return
        key = _canonical(path)
        if key in seen:
            return
        seen.add(key)
        try:
            if path.stat().st_size == 0:
                raise ValueError("empty audio")
            audio = mutagen.File(str(path))
            if audio is None or not math.isfinite(audio.info.length) or audio.info.length <= 0:
                raise ValueError("invalid audio or duration")
            result.tracks.append(Track(
                hashlib.sha256(key.encode("utf-8")).hexdigest(), str(path.resolve()),
                _tag(audio, ("TIT2", "title", "\xa9nam", "Title"), _text(path.stem, "Untitled")),
                _tag(audio, ("TPE1", "artist", "\xa9ART", "Author"), "Unknown Artist"),
                _tag(audio, ("TALB", "album", "\xa9alb", "WM/AlbumTitle"), "Unknown Album"),
                round(audio.info.length * 1000),
                path.suffix[1:].upper(), int(getattr(audio.info, "bitrate", 0) or 0),
                _sample_rate(audio, path), _cover(audio, path, cache_dir, result.errors),
            ))
        except (OSError, ValueError, mutagen.MutagenError, EOFError) as exc:
            result.errors.append(f"{path}: {exc}")

    for value in paths:
        if cancelled():
            break
        path = Path(value)
        try:
            path = path.resolve()
            if not path.exists():
                raise FileNotFoundError("source does not exist")
            if path.is_dir():
                if str(path) not in result.roots:
                    result.roots.append(str(path))
                for folder, dirs, files in os.walk(path, followlinks=False):
                    if cancelled():
                        break
                    dirs.sort()
                    for filename in sorted(files):
                        if cancelled():
                            break
                        inspect(Path(folder) / filename)
            else:
                inspect(path)
        except (OSError, RuntimeError, ValueError) as exc:
            result.errors.append(f"{path}: {exc}")
    return result


DEFAULT_PREFERENCES = {
    "theme": "dark", "volume": 0.65, "shuffle": False,
    "repeatMode": "off", "motionEnabled": False,
}


def _list(value):
    return value if isinstance(value, list) else []


def _local_path(value) -> bool:
    return isinstance(value, str) and bool(value) and len(value) <= 32768 and "\x00" not in value and Path(value).is_absolute()


def _loaded_track(row) -> Track | None:
    if not isinstance(row, dict):
        return None
    if not isinstance(row.get("id"), str) or not row["id"] or len(row["id"]) > 128 or not _local_path(row.get("path")):
        return None
    for name in ("durationMs", "bitrate", "sampleRate"):
        if type(row.get(name)) is not int or row[name] < 0:
            return None
    for name in ("title", "artist", "album", "format", "coverUrl"):
        if not isinstance(row.get(name), str):
            return None
    return Track(row["id"], row["path"], _text(row["title"], "Untitled"),
                 _text(row["artist"], "Unknown Artist"), _text(row["album"], "Unknown Album"),
                 row["durationMs"], _text(row["format"]), row["bitrate"], row["sampleRate"], row["coverUrl"])


def _playlist_name(name) -> bool:
    return isinstance(name, str) and bool(name.strip()) and len(name.strip()) <= 80 and not any(
        unicodedata.category(c).startswith("C") for c in name)


def _preferences(raw) -> dict:
    result = dict(DEFAULT_PREFERENCES)
    if not isinstance(raw, dict):
        return result
    if raw.get("theme") in ("dark", "light"):
        result["theme"] = raw["theme"]
    if raw.get("repeatMode") in ("off", "all", "one"):
        result["repeatMode"] = raw["repeatMode"]
    volume = raw.get("volume")
    if type(volume) in (int, float) and math.isfinite(volume):
        result["volume"] = max(0.0, min(1.0, volume))
    for name in ("shuffle", "motionEnabled"):
        if type(raw.get(name)) is bool:
            result[name] = raw[name]
    return result


class LibraryStore:
    """Cached startup does no audio IO. Mutate only on the owning controller thread."""

    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.state_path = self.directory / "library.json"
        self.tracks: list[Track] = []
        self.roots: list[str] = []
        self.favorites: set[str] = set()
        self.playlists: dict[str, list[str]] = {}
        self.preferences = dict(DEFAULT_PREFERENCES)
        self.errors: list[str] = []
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            return
        except (OSError, UnicodeError, ValueError, RecursionError) as exc:
            self.errors.append(f"Could not load library: {exc}")
            return
        if not isinstance(data, dict):
            self.errors.append("Invalid library state: expected object")
            return
        seen_ids, seen_paths = set(), set()
        for row in _list(data.get("tracks")):
            track = _loaded_track(row)
            if track is not None:
                key = os.path.normcase(os.path.normpath(track.path))
                if track.id not in seen_ids and key not in seen_paths:
                    self.tracks.append(track)
                    seen_ids.add(track.id)
                    seen_paths.add(key)
        self.roots = list(dict.fromkeys(r for r in _list(data.get("roots")) if _local_path(r)))
        self.favorites = {id for id in _list(data.get("favorites")) if isinstance(id, str) and id in seen_ids}
        playlists = data.get("playlists")
        if isinstance(playlists, dict):
            names = set()
            for name, ids in playlists.items():
                if _playlist_name(name) and name.casefold() not in names and isinstance(ids, list):
                    self.playlists[name] = list(dict.fromkeys(id for id in ids if isinstance(id, str) and id in seen_ids))
                    names.add(name.casefold())
        self.preferences = _preferences(data.get("preferences"))

    def save(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1, "tracks": [asdict(track) for track in self.tracks],
            "roots": self.roots, "favorites": sorted(self.favorites),
            "playlists": self.playlists, "preferences": self.preferences,
        }
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".tmp",
                                             dir=self.directory, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(data, stream, ensure_ascii=False, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.state_path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def merge(self, result: ScanResult) -> int:
        by_id = {track.id: track for track in self.tracks}
        added = 0
        for track in result.tracks:
            if track.id not in by_id:
                added += 1
            by_id[track.id] = track
        self.tracks = list(by_id.values())
        self.roots = list(dict.fromkeys([*self.roots, *result.roots]))
        self.save()
        return added

    def toggle_favorite(self, id: str) -> bool:
        if not any(track.id == id for track in self.tracks):
            return False
        if id in self.favorites:
            self.favorites.remove(id)
        else:
            self.favorites.add(id)
        self.save()
        return id in self.favorites

    def create_playlist(self, name: str) -> bool:
        if not isinstance(name, str) or any(unicodedata.category(c).startswith("C") for c in name):
            return False
        name = name.strip()
        if not name or len(name) > 80 or name.casefold() in {n.casefold() for n in self.playlists}:
            return False
        self.playlists[name] = []
        self.save()
        return True

    def add_to_playlist(self, name: str, id: str) -> bool:
        if name not in self.playlists or not any(track.id == id for track in self.tracks):
            return False
        if id in self.playlists[name]:
            return False
        self.playlists[name].append(id)
        self.save()
        return True

    def remove_from_library(self, id: str) -> bool:
        remaining = [track for track in self.tracks if track.id != id]
        if len(remaining) == len(self.tracks):
            return False
        self.tracks = remaining
        self.favorites.discard(id)
        self.playlists = {name: [item for item in ids if item != id] for name, ids in self.playlists.items()}
        self.save()
        return True
