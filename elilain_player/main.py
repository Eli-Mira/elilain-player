"""Native entry point and reproducible diagnostics."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFont, QIcon
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from .controller import ASSET_DIR, Controller

QML_DIR = Path(__file__).parent / "quick"


def create_engine(backend):
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"backend": backend})
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        raise RuntimeError("The player interface could not be loaded. Check the QML diagnostics above.")
    engine._backend = backend  # Python ownership must outlive QML property references.
    return engine


def main(argv=None):
    parser = argparse.ArgumentParser(description="EliLain Player — native, local music")
    parser.add_argument("--state-dir", type=Path, help="Isolate settings/library for verification")
    parser.add_argument("--doctor", action="store_true", help="Check Qt audio devices and packaged files")
    args = parser.parse_args(argv)
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName("EliLain Player")
    app.setOrganizationName("EliLain")
    app.setFont(QFont("Segoe UI", 10))
    app.setWindowIcon(QIcon(str(ASSET_DIR / "lain.ico")))
    QQuickStyle.setStyle("Basic")
    if args.doctor:
        import PySide6
        data = dict(python=sys.version.split()[0], qt=PySide6.__version__,
                    audioOutputs=len(QMediaDevices.audioOutputs()),
                    qmlPresent=(QML_DIR / "Main.qml").is_file(),
                    artworkPresent=(ASSET_DIR / "lain.png").is_file(), networkRequired=False)
        print(json.dumps(data, indent=2))
        return 0 if data["qmlPresent"] and data["artworkPresent"] and data["audioOutputs"] else 1
    store = None
    if args.state_dir:
        from .library import LibraryStore
        store = LibraryStore(args.state_dir)
    backend = Controller(store=store)
    engine = create_engine(backend)
    app.aboutToQuit.connect(backend.player.shutdown)
    result = app.exec()
    del engine
    return result


if __name__ == "__main__":
    raise SystemExit(main())
