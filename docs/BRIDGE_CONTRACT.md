# EliLain Player — implementation contract

Separate, offline desktop player. Never edit elilain-music, other projects or the user's audio files. Read audio; write only app settings/artwork cache.

## QML Python bridge (`backend`, required root property)

All properties below always exist; collections default empty and currentTrack defaults `{}`.
- `palette`: QVariantMap {bg, panel, raised, border, text, dim, faint, accent, signal, error}, dark by default. `theme`: str dark/light.
- `artworkBase`: str file URL ending `/`; bundled `lain.png`, `wired-city.png`, `wired-banner.png`, `backdrop-dark.png`, `backdrop-light.png`, `lain-reflection.png`.
- `tracks`: QVariantList of visible track maps, filtered by search and active view; `trackCount`: total library count; `viewTitle`: label for active view; `searchText`: str; `activeView`: str library/favorites/playlist:<name>.
- `playlists`: QVariantList {name, count}; `queue`: QVariantList of track maps in playback order; `queueIndex`: int (-1 empty).
- track map: {id, path, url, title, artist, album, durationMs, durationText, format, bitrate, sampleRate, coverUrl, favorite}; covers fall back to local Lain portrait. Map strings always safe to render as plain text.
- `currentTrack`: QVariantMap; `playing`: bool; `positionMs`: int; `durationMs`: int; `positionText`: str; `durationText`: str; `seekable`: bool; `volume`: double 0..1; `muted`: bool.
- `shuffle`: bool; `repeatMode`: str off/all/one; `scanBusy`: bool; `statusText`: str; `errorText`: str; `motionEnabled`: bool (false default); `levels`: QVariantList 24 floats in 0..1, based on decoded audio, zeros without playback.

Slots: `addFolder(QUrl)`, `addFiles(QVariantList of QUrls)`, `cancelScan()`, `setSearch(str)`, `selectView(str)`, `playTrack(str id)`, `togglePlayback()`, `nextTrack()`, `previousTrack()`, `seek(int ms)`, `setVolume(double)`, `toggleMute()`, `toggleShuffle()`, `cycleRepeat()`, `toggleFavorite(str id)`, `createPlaylist(str name)`, `addToPlaylist(str name, str id)`, `removeFromLibrary(str id)` (no filesystem deletion), `toggleTheme()`, `setMotion(bool)`, `revealCurrent()`, `clearError()`, `requestClose() -> bool`.
Signal `safeToClose()` after cancellation/thread completion; onClosing delegates requestClose; never delete a running scan worker.

Keyboard: Space play/pause except while editing; Ctrl O choose files; Ctrl Shift O choose folder; Ctrl F focus search; Ctrl Left/Right previous/next; Ctrl T theme; Esc closes overlays/cancels scan. Real FileDialog/FolderDialog call corresponding slots. Artwork and font dependencies are local-only.

## Pure library module (`elilain_player/library.py`)

`Track`: frozen dataclass fields id, path, title, artist, album, durationMs, format, bitrate, sampleRate, coverUrl. `to_dict()`: adds local `url` and mm:ss `durationText`.
`ScanResult`: dataclass tracks:list[Track], roots:list[str], errors:list[str].
`scan_paths(paths, cache_dir:Path, cancelled:Callable[[],bool] = ...) -> ScanResult`: inspect files/directories recursively, metadata via mutagen, no symlink loops, no source writes, dedup canonical paths; supported mp3/flac/wav/ogg/opus/m4a/aac/wma/aiff/alac. Invalid/zero-byte audio should be skipped and reported. Cache bounded embedded/sidecar artwork safely; coverUrl empty if absent (bridge supplies Lain fallback).
`LibraryStore(directory:Path)`: loads tolerant JSON state; fields tracks:list[Track], roots:list[str], favorites:set[str], playlists:dict[str,list[str]], preferences:dict (theme:'dark',volume:0.65,shuffle:false,repeatMode:'off',motionEnabled:false).
Methods `merge(ScanResult)->int` returns newly added count and saves, `save()`, `toggle_favorite(id)->bool`, `create_playlist(name)->bool` rejects blank/overlong/duplicate, `add_to_playlist(name,id)->bool`, `remove_from_library(id)->bool`. Atomic JSON persistence; missing files do not prevent opening the library, errors are recoverable. Playlists reference IDs, not mutable row indexes. Favorites and playback sequence must survive search/view changes.

## Boundaries

Parent owns playback.py, controller.py, main.py, packaging/assets/tools/README. Library worker owns library.py and tests/test_library.py only. Design worker owns quick/*.qml and tests/test_qml_design.py only. All code written before tests is forbidden; observe meaningful RED then GREEN. Do not publish or commit. Report actual commands/results and open caveats.
