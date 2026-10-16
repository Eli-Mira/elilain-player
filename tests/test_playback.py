from conftest import until
from PySide6.QtMultimedia import QMediaPlayer


def track(path, identity):
    return {"id": identity, "path": str(path), "title": identity}


def test_queue_navigation_and_repeat_end_semantics(qapp, audio_file):
    from elilain_player.playback import AudioPlayer
    player = AudioPlayer()
    player.set_volume(0)
    try:
        player.set_queue([track(audio_file, "a"), track(audio_file, "b")], "a")
        player.next()
        assert player.current["id"] == "b"
        player.previous()
        assert player.current["id"] == "a"
        player.next()
        player.handle_status(QMediaPlayer.MediaStatus.EndOfMedia)
        assert player.current["id"] == "b" and not player.playing
        player.cycle_repeat()
        assert player.repeat_mode == "all"
        player.handle_status(QMediaPlayer.MediaStatus.EndOfMedia)
        assert player.current["id"] == "a"
        player.cycle_repeat()
        assert player.repeat_mode == "one"
        player.handle_status(QMediaPlayer.MediaStatus.EndOfMedia)
        assert player.current["id"] == "a"
    finally:
        player.shutdown()


def test_shuffle_keeps_current_and_restores_original_queue(qapp, audio_file):
    from elilain_player.playback import AudioPlayer
    player = AudioPlayer()
    player.set_volume(0)
    original = [track(audio_file, n) for n in ["a", "b", "c", "d"]]
    try:
        player.set_queue(original, "c")
        player.toggle_shuffle()
        assert player.shuffle and player.current["id"] == "c"
        assert sorted(t["id"] for t in player.queue) == ["a", "b", "c", "d"]
        player.toggle_shuffle()
        assert not player.shuffle
        assert [t["id"] for t in player.queue] == ["a", "b", "c", "d"]
        assert player.current["id"] == "c"
    finally:
        player.shutdown()


def test_invalid_source_does_not_replace_a_valid_queue(qapp, audio_file, tmp_path):
    from elilain_player.playback import AudioPlayer
    player = AudioPlayer()
    player.set_volume(0)
    errors = []
    player.failed.connect(errors.append)
    try:
        player.set_queue([track(audio_file, "good")], "good")
        player.set_queue([track(tmp_path / "missing.wav", "bad")], "bad")
        assert player.current["id"] == "good"
        assert errors and "missing" in errors[-1].lower()
        player.set_queue([])
        assert not player.playing and player.current == {} and player.queue_index == -1
    finally:
        player.shutdown()


def test_volume_mute_and_actual_decoded_signal_levels(qapp, audio_file):
    from elilain_player.playback import AudioPlayer
    player = AudioPlayer()
    try:
        player.set_volume(2)
        assert player.volume == 1
        player.set_volume(-1)
        assert player.volume == 0
        player.toggle_mute()
        assert player.muted
        player.set_queue([track(audio_file, "tone")], "tone")
        until(lambda: any(value > 0.05 for value in player.levels))
        assert len(player.levels) == 24
        assert all(0 <= value <= 1 for value in player.levels)
        player.toggle()
        until(lambda: not player.playing)
        assert not any(player.levels)
    finally:
        player.shutdown()


def test_actual_local_audio_decode_pause_and_seek(qapp, audio_file):
    from elilain_player.playback import AudioPlayer
    player = AudioPlayer()
    player.set_volume(0)  # Decode actual audio without sounding the user's speakers.
    track = {"id": "acceptance", "path": str(audio_file), "title": "Acceptance tone"}
    try:
        player.set_queue([track], "acceptance")
        until(lambda: player.duration_ms > 0 and player.position_ms > 100)
        assert 5900 <= player.duration_ms <= 6100
        assert player.playing
        assert player.seekable
        player.toggle()
        until(lambda: not player.playing)
        player.seek(2000)
        until(lambda: abs(player.position_ms - 2000) < 250)
        assert player.current["id"] == "acceptance"
    finally:
        player.shutdown()


def test_real_end_of_media_advances_and_stops_at_queue_end(qapp, audio_file, tmp_path):
    import wave
    from elilain_player.playback import AudioPlayer
    short = tmp_path / "Real EOF acceptance.wav"
    with wave.open(str(audio_file), "rb") as source, wave.open(str(short), "wb") as destination:
        destination.setparams(source.getparams())
        destination.writeframes(source.readframes(4000))
    player = AudioPlayer()
    player.set_volume(0)
    ended = []
    player.media.mediaStatusChanged.connect(
        lambda status: ended.append(True) if status == QMediaPlayer.MediaStatus.EndOfMedia else None)
    try:
        player.set_queue([track(short, "first"), track(short, "second")], "first")
        until(lambda: len(ended) >= 2 and player.current["id"] == "second" and not player.playing)
        assert player.queue_index == 1
    finally:
        player.shutdown()

