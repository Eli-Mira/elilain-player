"""Real local audio decoding and transport; no network sources or pretend playback."""
from __future__ import annotations

import array
import math
import random
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioBufferOutput, QAudioFormat, QAudioOutput, QMediaPlayer


class AudioPlayer(QObject):
    changed = Signal()
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.media = QMediaPlayer(self)
        self.output = QAudioOutput(self)
        self.media.setAudioOutput(self.output)
        self._queue = []
        self._index = -1
        self._original = []
        self.shuffle = False
        self.repeat_mode = "off"
        self._levels = [0.0] * 24
        self.buffer_output = QAudioBufferOutput(self)
        self.media.setAudioBufferOutput(self.buffer_output)
        self.buffer_output.audioBufferReceived.connect(self._decode_levels)
        self.media.mediaStatusChanged.connect(self.handle_status)
        for signal in (self.media.positionChanged, self.media.durationChanged,
                       self.media.playbackStateChanged, self.media.seekableChanged):
            signal.connect(lambda *_: self.changed.emit())
        self.media.errorOccurred.connect(lambda _, text: self.failed.emit(text))

    @property
    def current(self):
        return dict(self._queue[self._index]) if 0 <= self._index < len(self._queue) else {}

    @property
    def position_ms(self):
        return self.media.position()

    @property
    def duration_ms(self):
        return self.media.duration()

    @property
    def playing(self):
        return self.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    @property
    def seekable(self):
        return self.media.isSeekable()

    def set_volume(self, value):
        self.output.setVolume(max(0.0, min(1.0, float(value))))
        self.changed.emit()

    @property
    def queue(self):
        return [dict(t) for t in self._queue]

    @property
    def queue_index(self):
        return self._index

    @property
    def volume(self):
        return self.output.volume()

    @property
    def muted(self):
        return self.output.isMuted()

    @property
    def levels(self):
        return list(self._levels) if self.playing else [0.0] * 24

    def set_queue(self, tracks, selected_id=None):
        tracks = [dict(t) for t in tracks]
        index = next((i for i, t in enumerate(tracks) if t["id"] == selected_id),
                     0 if tracks else -1)
        if index >= 0 and not Path(tracks[index]["path"]).is_file():
            self.failed.emit("This file is missing. Add its folder again or choose another track.")
            return False
        self._original = tracks
        self._queue = list(tracks)
        self._index = index
        if not tracks:
            self.shutdown()
        else:
            if self.shuffle:
                self._arrange_shuffled()
            self._play_index(self._index)
        self.changed.emit()
        return True

    def _play_index(self, index):
        if not 0 <= index < len(self._queue):
            return
        path = Path(self._queue[index]["path"]).resolve()
        if not path.is_file():
            self.failed.emit("This file is missing. Add its folder again or choose another track.")
            return
        self._index = index
        self._levels = [0.0] * 24
        self.media.setSource(QUrl.fromLocalFile(str(path)))
        self.media.play()
        self.changed.emit()

    def next(self, automatic=False):
        if not self._queue:
            return
        if automatic and self.repeat_mode == "one":
            self.media.setPosition(0)
            self.media.play()
        elif self._index + 1 < len(self._queue):
            self._play_index(self._index + 1)
        elif automatic and self.repeat_mode == "off":
            self.media.stop()
        else:
            self._play_index(0)
        self.changed.emit()

    def previous(self):
        if self.position_ms > 3000:
            self.seek(0)
        elif self._queue:
            self._play_index((self._index - 1) % len(self._queue))

    def handle_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.next(automatic=True)

    def _arrange_shuffled(self):
        current = self.current
        others = [t for t in self._original if t["id"] != current.get("id")]
        random.shuffle(others)
        self._queue = ([current] if current else []) + others
        self._index = 0 if self._queue else -1

    def toggle_shuffle(self):
        current_id = self.current.get("id")
        self.shuffle = not self.shuffle
        if self.shuffle:
            self._arrange_shuffled()
        else:
            self._queue = list(self._original)
            self._index = next((i for i, t in enumerate(self._queue) if t["id"] == current_id), -1)
        self.changed.emit()

    def cycle_repeat(self):
        modes = ("off", "all", "one")
        self.repeat_mode = modes[(modes.index(self.repeat_mode) + 1) % len(modes)]
        self.changed.emit()

    def toggle_mute(self):
        self.output.setMuted(not self.muted)
        self.changed.emit()

    def _decode_levels(self, buffer):
        # A real PCM amplitude meter, not a fabricated frequency spectrum.
        formats = {
            QAudioFormat.SampleFormat.UInt8: ("B", 128.0),
            QAudioFormat.SampleFormat.Int16: ("h", 32768.0),
            QAudioFormat.SampleFormat.Int32: ("i", 2147483648.0),
            QAudioFormat.SampleFormat.Float: ("f", 1.0),
        }
        spec = formats.get(buffer.format().sampleFormat())
        if not buffer.isValid() or not spec:
            self._levels = [0.0] * 24
        else:
            kind, scale = spec
            samples = array.array(kind)
            samples.frombytes(bytes(buffer.constData())[:buffer.byteCount()])
            step = max(1, len(samples) // 24)
            values = []
            for index in range(24):
                part = samples[index * step:(index + 1) * step]
                offset = 128 if kind == "B" else 0
                energy = sum(((sample - offset) / scale) ** 2 for sample in part)
                values.append(min(1.0, math.sqrt(energy / max(1, len(part))) * 2.0))
            self._levels = values
        self.changed.emit()

    def toggle(self):
        if self.playing:
            self.media.pause()
        elif self._index >= 0:
            self.media.play()

    def seek(self, value):
        if self.seekable:
            self.media.setPosition(max(0, min(self.duration_ms, int(value))))

    def shutdown(self):
        self.media.stop()
        self.media.setSource(QUrl())
        self._levels = [0.0] * 24
        self.changed.emit()
