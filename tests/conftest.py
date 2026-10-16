import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")

import math
import struct
import wave

import pytest
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setFont(QFont("Segoe UI", 10))
    yield app


@pytest.fixture
def audio_file(tmp_path):
    path = tmp_path / "Playback acceptance tone.wav"
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        output.writeframes(b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * n / 16000)))
                                   for n in range(16000 * 6)))
    return path


def until(condition, milliseconds=5000):
    for _ in range(milliseconds // 20):
        if condition():
            return
        QTest.qWait(20)
    assert condition(), "Expected Qt state transition did not occur"
