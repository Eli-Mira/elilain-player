"""Headless render + real-backend check: actual pixels, real audio, no claims from stubs."""
import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QEventLoop, QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QFont, QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

from elilain_player.controller import Controller  # noqa: E402
from elilain_player.library import LibraryStore  # noqa: E402
from elilain_player.main import QML_DIR  # noqa: E402


def pump(app, seconds):
    loop = QEventLoop()
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    loop.exec()
    app.processEvents()


def render(app, backend, size, out, title):
    diagnostics = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda errors: diagnostics.extend(str(e.toString()) for e in errors))
    engine.setInitialProperties({"backend": backend})
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        raise SystemExit(f"FAIL {title}: QML did not load — {diagnostics}")
    window = engine.rootObjects()[0]
    window.setWidth(size[0])
    window.setHeight(size[1])
    pump(app, 1.2)
    image = window.grabWindow()
    assert not image.isNull(), f"FAIL {title}: no pixels"
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(out))
    assert not diagnostics, f"FAIL {title}: QML diagnostics {diagnostics}"
    return window, engine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("outdir", type=Path)
    parser.add_argument("--music", type=Path, action="append", default=[],
                        help="Real local folder to scan (repeatable)")
    args = parser.parse_args()
    app = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
    app.setFont(QFont("Segoe UI", 10))
    QQuickStyle.setStyle("Basic")
    store = LibraryStore(Path(os.environ.get("TMPDIR", ".")) / "render-state")
    store.tracks, store.favorites, store.playlists = [], set(), {}
    backend = Controller(store=store)
    backend.setVolume(0)
    added = 0
    for folder in args.music:
        backend.addFolder(QUrl.fromLocalFile(str(folder)))
        for _ in range(400):
            if not backend.scanBusy:
                break
            pump(app, 0.05)
        added = backend.trackCount
    if backend.tracks:
        backend.playTrack(backend.tracks[0]["id"])
        pump(app, 1.6)
    report = {"scannedTracks": added, "renders": []}
    for name, size in (("dark-1380", (1380, 900)), ("compact-1040", (1040, 720))):
        backend.store.preferences["theme"] = "dark"
        backend.preferencesChanged.emit()
        window, engine = render(app, backend, size, args.outdir / f"{name}.png", name)
        report["renders"].append({"file": f"{name}.png", "size": list(size), "diagnostics": 0})
        if name == "dark-1380":
            peak = max(backend.levels or [0.0])
            report["playing"] = backend.playing
            report["decodedLevelPeak"] = round(peak, 4)
            report["durationMs"] = backend.durationMs
        del window, engine
    backend.store.preferences["theme"] = "light"
    backend.preferencesChanged.emit()
    render(app, backend, (1380, 900), args.outdir / "light-1380.png", "light-1380")
    report["renders"].append({"file": "light-1380.png", "size": [1380, 900], "diagnostics": 0})
    backend.requestClose()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()