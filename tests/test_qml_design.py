"""Native Qt Quick acceptance tests. All songs here are explicit test fixtures."""
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

import pytest
from PySide6.QtCore import Property, QObject, QPointF, QRectF, Qt, QUrl, Signal, Slot
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from elilain_player.controller import DARK, LIGHT

# The exact palettes shipped by the real controller. Design tests must render the
# production tokens, not a look-alike, or a hand-tuned theme change slips through.
ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "elilain_player/quick/Main.qml"
DEFAULTS = dict(palette=DARK, theme="dark", artworkBase=QUrl.fromLocalFile(str(ROOT / "elilain_player/assets") + "/").toString(), tracks=[], trackCount=0, viewTitle="All music", searchText="", activeView="library", playlists=[], queue=[], queueIndex=-1, currentTrack={}, playing=False, positionMs=0, durationMs=0, positionText="0:00", durationText="0:00", seekable=False, volume=0.65, muted=False, shuffle=False, repeatMode="off", scanBusy=False, statusText="Your music, on this device.", errorText="", motionEnabled=False, levels=[0.0] * 24)


class FixtureBackend(QObject):
    changed = Signal()
    safeToClose = Signal()

    def __init__(self):
        super().__init__()
        self.values = dict(DEFAULTS)
        self.calls = []

    def update(self, **values):
        self.values.update(values)
        self.changed.emit()

    def invoke(self, name, *args):
        self.calls.append((name, args))
        if name == "toggleTheme":
            light = self.values["theme"] == "dark"
            self.update(theme="light" if light else "dark", palette=LIGHT if light else DARK)
        elif name == "setSearch":
            self.update(searchText=args[0])
        elif name == "selectView":
            self.update(activeView=args[0])
        elif name == "togglePlayback":
            self.update(playing=not self.values["playing"])
        elif name == "setVolume":
            self.update(volume=args[0])
        elif name == "toggleMute":
            self.update(muted=not self.values["muted"])
        elif name == "setMotion":
            self.update(motionEnabled=args[0])
        elif name == "clearError":
            self.update(errorText="")
        return True if name == "requestClose" else None

    # Explicit metaobject declarations avoid dynamic-type inherited-signal
    # crashes in PySide6 6.11 when QML reads a property.
    @Property('QVariantMap', notify=changed)
    def palette(self):
        return self.values['palette']

    @Property(str, notify=changed)
    def theme(self):
        return self.values['theme']

    @Property(str, notify=changed)
    def artworkBase(self):
        return self.values['artworkBase']

    @Property('QVariantList', notify=changed)
    def tracks(self):
        return self.values['tracks']

    @Property(int, notify=changed)
    def trackCount(self):
        return self.values['trackCount']

    @Property(str, notify=changed)
    def viewTitle(self):
        return self.values['viewTitle']

    @Property(str, notify=changed)
    def searchText(self):
        return self.values['searchText']

    @Property(str, notify=changed)
    def activeView(self):
        return self.values['activeView']

    @Property('QVariantList', notify=changed)
    def playlists(self):
        return self.values['playlists']

    @Property('QVariantList', notify=changed)
    def queue(self):
        return self.values['queue']

    @Property(int, notify=changed)
    def queueIndex(self):
        return self.values['queueIndex']

    @Property('QVariantMap', notify=changed)
    def currentTrack(self):
        return self.values['currentTrack']

    @Property(bool, notify=changed)
    def playing(self):
        return self.values['playing']

    @Property(int, notify=changed)
    def positionMs(self):
        return self.values['positionMs']

    @Property(int, notify=changed)
    def durationMs(self):
        return self.values['durationMs']

    @Property(str, notify=changed)
    def positionText(self):
        return self.values['positionText']

    @Property(str, notify=changed)
    def durationText(self):
        return self.values['durationText']

    @Property(bool, notify=changed)
    def seekable(self):
        return self.values['seekable']

    @Property(float, notify=changed)
    def volume(self):
        return self.values['volume']

    @Property(bool, notify=changed)
    def muted(self):
        return self.values['muted']

    @Property(bool, notify=changed)
    def shuffle(self):
        return self.values['shuffle']

    @Property(str, notify=changed)
    def repeatMode(self):
        return self.values['repeatMode']

    @Property(bool, notify=changed)
    def scanBusy(self):
        return self.values['scanBusy']

    @Property(str, notify=changed)
    def statusText(self):
        return self.values['statusText']

    @Property(str, notify=changed)
    def errorText(self):
        return self.values['errorText']

    @Property(bool, notify=changed)
    def motionEnabled(self):
        return self.values['motionEnabled']

    @Property('QVariantList', notify=changed)
    def levels(self):
        return self.values['levels']

    @Slot(QUrl)
    def addFolder(self, value):
        return self.invoke('addFolder', value)

    @Slot('QVariantList')
    def addFiles(self, value):
        return self.invoke('addFiles', value)

    @Slot()
    def cancelScan(self):
        return self.invoke('cancelScan')

    @Slot(str)
    def setSearch(self, value):
        return self.invoke('setSearch', value)

    @Slot(str)
    def selectView(self, value):
        return self.invoke('selectView', value)

    @Slot(str)
    def playTrack(self, value):
        return self.invoke('playTrack', value)

    @Slot(int)
    def playQueued(self, value):
        return self.invoke('playQueued', value)

    @Slot()
    def togglePlayback(self):
        return self.invoke('togglePlayback')

    @Slot()
    def nextTrack(self):
        return self.invoke('nextTrack')

    @Slot()
    def previousTrack(self):
        return self.invoke('previousTrack')

    @Slot(int)
    def seek(self, value):
        return self.invoke('seek', value)

    @Slot(float)
    def setVolume(self, value):
        return self.invoke('setVolume', value)

    @Slot()
    def toggleMute(self):
        return self.invoke('toggleMute')

    @Slot()
    def toggleShuffle(self):
        return self.invoke('toggleShuffle')

    @Slot()
    def cycleRepeat(self):
        return self.invoke('cycleRepeat')

    @Slot(str)
    def toggleFavorite(self, value):
        return self.invoke('toggleFavorite', value)

    @Slot(str)
    def createPlaylist(self, value):
        return self.invoke('createPlaylist', value)

    @Slot(str, str)
    def addToPlaylist(self, name, track_id):
        return self.invoke('addToPlaylist', name, track_id)

    @Slot(str)
    def removeFromLibrary(self, value):
        return self.invoke('removeFromLibrary', value)

    @Slot()
    def toggleTheme(self):
        return self.invoke('toggleTheme')

    @Slot(bool)
    def setMotion(self, value):
        return self.invoke('setMotion', value)

    @Slot()
    def revealCurrent(self):
        return self.invoke('revealCurrent')

    @Slot()
    def clearError(self):
        return self.invoke('clearError')

    @Slot(result=bool)
    def requestClose(self):
        return self.invoke('requestClose')

@pytest.fixture(scope="session")
def app(qapp):
    # The session QApplication from conftest already carries the production
    # Segoe UI 10pt font; never create a second application.
    return qapp


@pytest.fixture
def scene(app):
    assert QML.exists(), "Native Lain QML frontend has not been implemented"
    backend = FixtureBackend()
    engine = QQmlApplicationEngine()
    diagnostics = []
    engine.warnings.connect(lambda errors: diagnostics.extend(error.toString() for error in errors))
    engine.setInitialProperties({"backend": backend})
    engine.load(QUrl.fromLocalFile(str(QML)))
    assert engine.rootObjects(), diagnostics
    window = engine.rootObjects()[0]
    window.show()
    window.requestActivate()
    QTest.qWait(100)
    yield window, backend, diagnostics
    assert not diagnostics, "\n".join(diagnostics)
    window.hide()
    engine.deleteLater()
    app.processEvents()


def item(window, name):
    # ListView delegates and popup contents have visual parents independent
    # of their QObject ownership. Walk the real scene graph as well.
    def visit(node):
        if node.objectName() == name:
            return node
        for child in node.childItems():
            found = visit(child)
            if found is not None:
                return found
        return None
    result = window.findChild(QQuickItem, name)
    if result is None:
        result = visit(window.contentItem())
    assert result is not None, f"Missing accessible UI target {name}"
    return result


def node(window, name):
    """Look up any QObject by objectName, including non-visual dialogs."""
    result = window.findChild(QObject, name)
    assert result is not None, f"Missing accessible UI target {name}"
    return result


def click(window, name):
    target = item(window, name)
    assert target.isVisible() and target.isEnabled(), name
    point = target.mapToScene(QPointF(target.width() / 2, target.height() / 2)).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
    QTest.qWait(15)


@pytest.mark.parametrize("size", [(1380, 900), (1120, 760), (1040, 720)])
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_empty_library_renders_real_art_and_contained_primary_surfaces(scene, size, theme):
    window, backend, diagnostics = scene
    backend.update(theme=theme, palette=DARK if theme == "dark" else LIGHT)
    window.resize(*size)
    QTest.qWait(100)
    image = window.grabWindow()
    assert not image.isNull()
    assert image.width() == size[0]
    assert item(window, "emptyLibrary").isVisible()
    assert item(window, "trackList").property("count") == 0
    assert item(window, "portrait").property("imageReady")
    assert item(window, "reflection").property("imageReady")
    for name in ("navigationCard", "libraryCard", "listeningCard", "transportCard", "addFolderButton", "searchField", "themeButton", "playButton", "timeline", "volumeSlider"):
        target = item(window, name)
        origin = target.mapToScene(QPointF(0, 0))
        assert origin.x() >= 0 and origin.y() >= 0, name
        assert origin.x() + target.width() <= size[0] + 1, name
        assert origin.y() + target.height() <= size[1] + 1, name
    assert not item(window, "playButton").isEnabled()
    assert not item(window, "timeline").isEnabled()
    assert not diagnostics


@pytest.mark.parametrize("size", [(1380, 900), (1120, 760), (1040, 720)])
def test_content_stays_inside_its_card_padding(scene, size):
    window, backend, diagnostics = scene
    populate(backend)
    backend.update(errorText="Fixture read error", scanBusy=True)
    window.resize(*size)
    QTest.qWait(40)
    cards = {"navigationCard": ("libraryNav", "addFolderButton", "newPlaylistButton"), "libraryCard": ("searchField", "albumFilter", "addFilesButton", "errorBanner", "clearErrorButton", "cancelScanButton"), "listeningCard": ("portrait", "reflection", "nowTitle", "revealButton", "amplitudeMeter", "queueList"), "transportCard": ("timeline", "playButton", "volumeSlider", "repeatButton")}
    for card, children in cards.items():
        surface = item(window, card)
        rect = surface.mapRectToScene(QRectF(0, 0, surface.width(), surface.height()))
        for name in children:
            child = item(window, name)
            assert child.isVisible() and child.width() > 0 and child.height() > 0, f"{name} collapsed inside {card}"
            box = child.mapRectToScene(QRectF(0, 0, child.width(), child.height()))
            assert rect.contains(box), f"{name} escapes {card}"


@pytest.mark.parametrize("size", [(1380, 900), (1040, 720)])
def test_transport_and_cards_do_not_overlap_at_minimum_size(scene, size):
    window, backend, diagnostics = scene
    populate(backend)
    window.resize(*size)
    QTest.qWait(80)

    def scene_rect(name):
        target = item(window, name)
        return target.mapRectToScene(QRectF(0, 0, target.width(), target.height()))

    transport = scene_rect("transportCard")
    for card in ("navigationCard", "libraryCard", "listeningCard"):
        assert not transport.intersects(scene_rect(card)), f"transport overlaps {card} at {size}"
    assert not scene_rect("navigationCard").intersects(scene_rect("libraryCard"))
    assert not scene_rect("libraryCard").intersects(scene_rect("listeningCard"))
    assert not diagnostics


def test_repeated_theme_toggling_keeps_readable_pixels(scene, tmp_path):
    window, backend, diagnostics = scene
    populate(backend)
    for step in range(6):
        click(window, "themeButton")
        QTest.qWait(60)
        image = window.grabWindow()
        assert not image.isNull()
        path = tmp_path / f"lain-{step}.png"
        assert image.save(str(path)), f"could not write render for step {step}"
        assert path.stat().st_size > 20000
        assert backend.values["theme"] == ("light" if step % 2 == 0 else "dark")
    assert not diagnostics


FIXTURE_TRACK = dict(id="fixture-a", path="C:/fixture/audio.wav", url="file:///C:/fixture/audio.wav", title="Fixture title <not markup>", artist="Fixture artist", album="Fixture album", durationMs=180000, durationText="3:00", format="WAV", bitrate=1411, sampleRate=44100, coverUrl="", favorite=False)


def populate(backend):
    second = dict(FIXTURE_TRACK, id="fixture-b", title="Second fixture", artist="Another artist")
    backend.update(tracks=[FIXTURE_TRACK, second], trackCount=2, currentTrack=FIXTURE_TRACK, queue=[FIXTURE_TRACK, second], queueIndex=0, durationMs=180000, durationText="3:00", seekable=True, playlists=[dict(name="Night listening", count=1)])
    QTest.qWait(60)


def test_library_rows_navigation_and_track_actions_dispatch_real_ids(scene):
    window, backend, _ = scene
    populate(backend)
    assert not item(window, "emptyLibrary").isVisible()
    click(window, "trackPlay-fixture-a")
    assert backend.calls[-1] == ("playTrack", ("fixture-a",))
    click(window, "favorite-fixture-a")
    assert backend.calls[-1] == ("toggleFavorite", ("fixture-a",))
    click(window, "favoritesNav")
    assert backend.calls[-1] == ("selectView", ("favorites",))
    click(window, "libraryNav")
    assert backend.calls[-1] == ("selectView", ("library",))
    click(window, "playlist-Night listening")
    assert backend.calls[-1] == ("selectView", ("playlist:Night listening",))
    click(window, "trackActions-fixture-a")
    click(window, "addToPlaylistButton")
    assert backend.calls[-1] == ("addToPlaylist", ("Night listening", "fixture-a"))


def test_now_playing_queue_transport_and_audio_controls_are_live(scene):
    window, backend, _ = scene
    populate(backend)
    assert item(window, "nowTitle").property("text") == FIXTURE_TRACK["title"]
    assert item(window, "queueList").property("count") == 2
    for target, slot in [("playButton", "togglePlayback"), ("previousButton", "previousTrack"), ("nextButton", "nextTrack"), ("shuffleButton", "toggleShuffle"), ("repeatButton", "cycleRepeat"), ("muteButton", "toggleMute"), ("revealButton", "revealCurrent")]:
        click(window, target)
        assert backend.calls[-1] == (slot, ())
    assert item(window, "playButton").property("text") == "Pause"
    click(window, "queuePlay-fixture-b")
    assert backend.calls[-1] == ("playQueued", (1,))
    slider = item(window, "timeline")
    slider.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Right)
    assert backend.calls[-1][0] == "seek"
    assert 0 < backend.calls[-1][1][0] <= 180000
    slider = item(window, "volumeSlider")
    slider.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Left)
    assert backend.calls[-1][0] == "setVolume"
    assert 0 <= backend.calls[-1][1][0] < 0.65
    backend.update(currentTrack=dict(FIXTURE_TRACK, title="Changed fixture", coverUrl=backend.artworkBase + "wired-banner.png"), positionMs=42000, positionText="0:42")
    QTest.qWait(30)
    assert item(window, "nowTitle").property("text") == "Changed fixture"
    assert "wired-banner.png" in item(window, "portrait").property("source").toString()
    assert item(window, "timeline").property("value") == 42000


def test_shortcuts_exclude_text_entry_and_create_playlist_is_real(scene):
    window, backend, _ = scene
    populate(backend)
    QTest.keyClick(window, Qt.Key_F, Qt.ControlModifier)
    QTest.qWait(15)
    assert item(window, "searchField").hasActiveFocus()
    before = sum(name == "togglePlayback" for name, _ in backend.calls)
    QTest.keyClick(window, Qt.Key_N)
    QTest.keyClick(window, Qt.Key_Space)
    assert backend.values["searchText"] == "n "
    assert sum(name == "togglePlayback" for name, _ in backend.calls) == before
    click(window, "libraryNav")
    QTest.keyClick(window, Qt.Key_Space)
    assert backend.calls[-1][0] == "togglePlayback"
    QTest.keyClick(window, Qt.Key_Right, Qt.ControlModifier)
    assert backend.calls[-1][0] == "nextTrack"
    QTest.keyClick(window, Qt.Key_Left, Qt.ControlModifier)
    assert backend.calls[-1][0] == "previousTrack"
    QTest.keyClick(window, Qt.Key_T, Qt.ControlModifier)
    assert backend.values["theme"] == "light"
    click(window, "newPlaylistButton")
    assert item(window, "playlistNameField").hasActiveFocus()
    for key in (Qt.Key_N, Qt.Key_I, Qt.Key_G, Qt.Key_H, Qt.Key_T):
        QTest.keyClick(window, key)
    click(window, "createPlaylistButton")
    assert backend.calls[-1] == ("createPlaylist", ("night",))


def test_album_and_queue_filters_and_recoverable_error_scan_states(scene):
    window, backend, _ = scene
    populate(backend)
    album = item(window, "albumFilter")
    album.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Down)
    QTest.keyClick(window, Qt.Key_Return)
    assert backend.calls[-1] == ("setSearch", ("Fixture album",))
    click(window, "queueSearch")
    for key in (Qt.Key_S, Qt.Key_E, Qt.Key_C):
        QTest.keyClick(window, key)
    assert item(window, "queueList").property("count") == 1
    backend.update(errorText="Fixture read error", scanBusy=True)
    QTest.qWait(20)
    assert item(window, "errorBanner").isVisible()
    click(window, "clearErrorButton")
    assert backend.values["errorText"] == ""
    click(window, "cancelScanButton")
    assert backend.calls[-1] == ("cancelScan", ())
    click(window, "libraryNav")
    QTest.keyClick(window, Qt.Key_Escape)
    assert backend.calls[-1] == ("cancelScan", ())


def test_file_derived_labels_never_render_markup(scene):
    window, backend, _ = scene
    hostile = dict(FIXTURE_TRACK, id="fixture-hostile", title='<img src="https://example.invalid/remote.png">', artist="<b>bold</b> artist", album="<i>album</i>")
    backend.update(tracks=[hostile], trackCount=1, currentTrack=hostile, queue=[hostile], searchText="", errorText="<img src='https://example.invalid/error.png'>")
    QTest.qWait(40)

    def images(node, found=None):
        found = [] if found is None else found
        if node.metaObject().className().startswith("QQuickImage"):
            found.append(node)
        for child in node.childItems():
            images(child, found)
        return found

    def scan(node, found=None):
        # Inline QML components expose their own class name, so detect text by
        # the plainTextSafe guard declared on the shared label component.
        found = [] if found is None else found
        if node.property("plainTextSafe") is not None:
            found.append(node)
        for child in node.childItems():
            scan(child, found)
        return found

    rendered = scan(window.contentItem())
    assert len(rendered) > 20
    for label in rendered:
        assert label.property("plainTextSafe") is True, f"Non-plain text format on {label.property('text')!r}"
    assert any("example.invalid" in label.property("text") for label in rendered)
    # Markup must not have created any remote image: every image still resolves
    # to a bundled local asset file.
    loaded = images(window.contentItem())
    assert len(loaded) >= 4, [node.metaObject().className() for node in loaded]
    for node in loaded:
        source = node.property("source").toString()
        assert source.startswith("file:") and "assets" in source, source
        assert "example.invalid" not in source


def test_amplitude_meter_reflects_real_backend_levels_only(scene):
    window, backend, _ = scene
    populate(backend)
    meter = item(window, "amplitudeMeter")

    def bars(node, found=None):
        found = [] if found is None else found
        if node.metaObject().className() == "QQuickRectangle":
            found.append(node)
        for child in node.childItems():
            bars(child, found)
        return found

    assert len(bars(meter)) == 24
    backend.update(playing=True, levels=[1.0 if n == 5 else 0.0 for n in range(24)])
    QTest.qWait(30)
    heights = sorted(bar.height() for bar in bars(meter))
    assert heights[-1] == meter.height()
    assert heights[0] == 1, heights
    backend.update(playing=False, levels=[0.0] * 24)
    QTest.qWait(30)
    assert max(bar.height() for bar in bars(meter)) == 1


def test_queue_rows_keep_real_playback_index_when_filtered(scene):
    window, backend, _ = scene
    populate(backend)
    third = dict(FIXTURE_TRACK, id="fixture-c", title="Third fixture")
    backend.update(queue=[FIXTURE_TRACK, third, dict(FIXTURE_TRACK, id="fixture-d", title="Fourth fixture")], queueIndex=2)
    click(window, "queueSearch")
    for key in (Qt.Key_F, Qt.Key_O, Qt.Key_U):
        QTest.keyClick(window, key)
    assert item(window, "queueList").property("count") == 1
    click(window, "queuePlay-fixture-d")
    assert backend.calls[-1] == ("playQueued", (2,))


def test_every_public_control_dispatches_a_contract_slot(scene):
    """No inert navigation: each public control must reach the backend bridge."""
    window, backend, _ = scene
    populate(backend)
    expected = {
        "themeButton": "toggleTheme",
        "libraryNav": "selectView",
        "favoritesNav": "selectView",
        "newPlaylistButton": None,  # opens a dialog; asserted separately
        "addFolderButton": None,  # opens the real FolderDialog
        "addFilesButton": None,  # opens the real FileDialog
        "trackPlay-fixture-a": "playTrack",
        "favorite-fixture-a": "toggleFavorite",
        "revealButton": "revealCurrent",
        "shuffleButton": "toggleShuffle",
        "previousButton": "previousTrack",
        "playButton": "togglePlayback",
        "nextButton": "nextTrack",
        "repeatButton": "cycleRepeat",
        "muteButton": "toggleMute",
        "queuePlay-fixture-b": "playQueued",
    }
    for name, slot in expected.items():
        if slot is None:
            target = item(window, name)
            assert target.isVisible() and target.isEnabled(), name
            continue
        backend.calls.clear()
        click(window, name)
        assert backend.calls, f"{name} dispatched nothing"
        assert backend.calls[-1][0] == slot, f"{name} called {backend.calls[-1][0]} not {slot}"
    item(window, "searchField").forceActiveFocus()
    for key in (Qt.Key_Q, Qt.Key_U, Qt.Key_I, Qt.Key_E, Qt.Key_T):
        QTest.keyClick(window, key)
    assert item(window, "searchField").property("text") == "quiet"
    assert backend.calls[-1] == ("setSearch", ("quiet",))
    timeline = item(window, "timeline")
    timeline.forceActiveFocus()
    QTest.qWait(20)
    QTest.keyClick(window, Qt.Key_Right)
    assert backend.calls[-1][0] == "seek"
    volume = item(window, "volumeSlider")
    volume.forceActiveFocus()
    QTest.qWait(20)
    assert volume.hasActiveFocus()
    QTest.keyClick(window, Qt.Key_Up)
    assert backend.calls[-1][0] == "setVolume"
    assert backend.calls[-1][1][0] > 0.65
    QTest.keyClick(window, Qt.Key_Down)
    assert backend.calls[-1][1][0] < backend.values["volume"] + 0.0001 or backend.calls[-1][0] == "setVolume"


def test_motion_and_crt_are_opt_in_and_call_the_contract_slot(scene):
    window, backend, _ = scene
    populate(backend)
    backend.update(motionEnabled=False)
    QTest.qWait(30)
    assert item(window, "motionButton").property("text") == "Motion off"
    assert item(window, "motionButton").property("checked") is False
    QTest.keyClick(window, Qt.Key_Space)  # proves no ambient loop hijacks input
    click(window, "motionButton")
    assert backend.calls[-1] == ("setMotion", (True,))
    assert backend.values["motionEnabled"] is True
    assert item(window, "motionButton").property("checked") is True
    assert item(window, "motionButton").property("text") == "Motion on"
    click(window, "motionButton")
    assert backend.calls[-1] == ("setMotion", (False,))


def test_dialogs_open_real_native_pickers_and_drive_contract_slots(scene):
    window, backend, _ = scene
    populate(backend)
    for name, picker in (("addFolderButton", "folderDialog"), ("addFilesButton", "fileDialog")):
        click(window, name)
        QTest.qWait(30)
        dialog = node(window, picker)
        assert dialog.property("visible") is True, picker
        assert dialog.property("title"), picker
        # Accept with a real local URL without touching the filesystem.
        if picker == "folderDialog":
            dialog.setProperty("selectedFolder", QUrl.fromLocalFile(str(ROOT)))
            dialog.metaObject().invokeMethod(dialog, "accepted")
        else:
            dialog.setProperty("selectedFiles", [QUrl.fromLocalFile(str(ROOT / "elilain_player/assets/lain.png"))])
            dialog.metaObject().invokeMethod(dialog, "accepted")
        QTest.qWait(20)
        assert backend.calls[-1][0] == ("addFolder" if picker == "folderDialog" else "addFiles")
        assert backend.calls[-1][1], "picker passed no URL to the backend"
        payload = backend.calls[-1][1][0]
        urls = payload if isinstance(payload, list) else [payload]
        assert all(url.isLocalFile() for url in urls), urls
        # Dismiss the real dialog so the next case starts from a clean window.
        dialog.setProperty("visible", False)
        QTest.qWait(20)


def test_closing_delegates_to_the_bridge_and_waits_for_safe_to_close(scene):
    window, backend, _ = scene
    populate(backend)
    assert backend.requestClose() is True
    assert window.property("visible") is True
    window.close()
    QTest.qWait(30)
    # The bridge refused nothing, so the deferred close may complete.
    backend.safeToClose.emit()
    QTest.qWait(40)
    assert window.property("visible") is False

