import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: root
    required property QtObject backend
    width: 1380; height: 900
    minimumWidth: 1040; minimumHeight: 720
    visible: true
    title: "lain. / local player"
    color: p.bg
    font.family: "Segoe UI"
    font.pointSize: 10
    readonly property var p: backend.palette
    readonly property bool light: backend.theme === "light"
    readonly property bool compact: width < 1180
    readonly property bool hasTrack: !!backend.currentTrack.id
    readonly property int gutter: 24
    readonly property int navWidth: compact ? 166 : 188
    readonly property int artWidth: compact ? 286 : 334
    property bool closingApproved: false
    property var actionTrack: ({})
    readonly property bool editingText: {
        let focused = root.activeFocusItem
        while (focused) {
            if (typeof focused.cursorPosition === "number" && typeof focused.text === "string") return true
            focused = focused.parent
        }
        return false
    }
    readonly property bool overlayOpen: newPlaylist.visible || trackActions.visible || fileDialog.visible || folderDialog.visible
    readonly property var albumOptions: ["All albums"].concat(Array.from(new Set(backend.tracks.map(t => t.album).filter(a => !!a))).sort())
    Shortcut { sequence: "Ctrl+F"; enabled: !root.overlayOpen; onActivated: search.forceActiveFocus(Qt.ShortcutFocusReason) }
    Shortcut { sequence: "Ctrl+O"; onActivated: fileDialog.open() }
    Shortcut { sequence: "Ctrl+Shift+O"; onActivated: folderDialog.open() }
    Shortcut { sequence: "Ctrl+T"; onActivated: root.backend.toggleTheme() }
    Shortcut { sequence: "Ctrl+Left"; enabled: root.hasTrack && !root.overlayOpen; onActivated: root.backend.previousTrack() }
    Shortcut { sequence: "Ctrl+Right"; enabled: root.hasTrack && !root.overlayOpen; onActivated: root.backend.nextTrack() }
    Shortcut { sequence: "Space"; enabled: root.hasTrack && !root.editingText && !root.overlayOpen; onActivated: root.backend.togglePlayback() }
    Shortcut { sequence: "Escape"; enabled: !root.overlayOpen; onActivated: { if (root.backend.scanBusy) root.backend.cancelScan(); else { search.clear(); root.backend.setSearch("") } } }

    onClosing: function(close) { close.accepted = closingApproved || backend.requestClose() }
    Connections {
        target: root.backend
        function onSafeToClose() { root.closingApproved = true; root.close() }
    }

    component Copy: Text {
        // File-derived tags are never treated as markup, so a hostile title
        // cannot pull a remote image into an offline app.
        color: root.p.text
        font.family: "Segoe UI"; font.pixelSize: 14
        textFormat: Text.PlainText
        elide: Text.ElideRight
        readonly property bool plainTextSafe: textFormat === Text.PlainText
    }
    component Micro: Copy {
        font.family: "Consolas"; font.pixelSize: 11
        font.letterSpacing: 1.3
        color: root.p.dim
    }
    component Field: TextField {
        id: field
        color: root.p.text; placeholderTextColor: root.p.dim
        selectionColor: root.p.accent; selectedTextColor: root.p.bg
        leftPadding: 12; rightPadding: 12; implicitHeight: 38
        background: Rectangle { color: root.light ? "#95ffffff" : "#600b1222"; radius: 10; border.width: field.activeFocus ? 2 : 1; border.color: field.activeFocus ? root.p.accent : root.p.border }
    }
    component Select: ComboBox {
        id: select
        implicitHeight: 36
        leftPadding: 12; rightPadding: 24
        contentItem: Copy { text: select.displayText; font.pixelSize: 12; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: 9; color: root.light ? "#f1f4f9" : "#172338"; border.width: select.visualFocus ? 2 : 1; border.color: select.visualFocus ? root.p.accent : root.p.border }
        indicator: Copy { x: select.width - 20; y: (select.height - height) / 2; text: "⌄"; color: root.p.dim }
        delegate: ItemDelegate {
            id: option
            required property var modelData
            width: select.width
            contentItem: Copy { text: select.textRole ? option.modelData[select.textRole] : option.modelData; font.pixelSize: 13 }
            background: Rectangle { color: option.highlighted || option.hovered ? root.p.raised : (root.light ? "#f4f6fa" : "#172338") }
        }
        popup: Popup {
            y: select.height + 4; width: select.width; padding: 4
            implicitHeight: Math.min(contentItem.implicitHeight + 8, 240)
            background: Rectangle { color: root.light ? "#f4f6fa" : "#172338"; radius: 9; border.color: root.p.border }
            contentItem: ListView { clip: true; implicitHeight: contentHeight; model: select.popup.visible ? select.delegateModel : null; currentIndex: select.highlightedIndex; ScrollBar.vertical: ScrollBar {} }
        }
    }
    component Glass: Rectangle {
        radius: 20; color: root.p.panel
        border.color: root.light ? "#809daac0" : "#40576a89"
        border.width: 1
        clip: true
    }
    component QuietButton: Button {
        id: control
        property bool primary: false
        implicitHeight: 40
        implicitWidth: Math.max(40, label.implicitWidth + 26)
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: text
        opacity: enabled ? 1 : 0.42
        contentItem: Copy {
            id: label
            text: control.text
            color: control.primary ? (root.light ? "#ffffff" : "#172336") : root.p.text
            font.pixelSize: 13; font.weight: control.primary ? Font.DemiBold : Font.Normal
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: 10
            color: control.primary ? root.p.accent : control.down ? root.p.raised : control.hovered || control.checked ? (root.light ? "#dbe1ed" : "#354255") : "transparent"
            border.width: control.visualFocus ? 2 : 1
            border.color: control.visualFocus ? root.p.accent : control.primary ? root.p.accent : (control.hovered || control.checked ? root.p.border : "transparent")
        }
        ToolTip.visible: hovered && text.length > 0
        ToolTip.text: text
        ToolTip.delay: 650
    }
    component MeterSlider: Slider {
        id: slider
        // Slider.onMoved omits vertical key presses, so watch value ourselves and
        // skip echoes of a value we already reported to the backend.
        property real lastSent: NaN
        signal reported(real reportedValue)
        implicitHeight: 32
        hoverEnabled: true
        opacity: enabled ? 1 : 0.45
        Keys.onUpPressed: slider.increase()
        Keys.onDownPressed: slider.decrease()
        onValueChanged: {
            if (!(pressed || activeFocus)) { lastSent = NaN; return }
            if (Math.abs(value - lastSent) < 0.0001) return
            lastSent = value
            slider.reported(value)
        }
        background: Rectangle {
            x: slider.leftPadding; y: slider.topPadding + slider.availableHeight / 2 - height / 2
            width: slider.availableWidth; height: 4; radius: 2
            color: root.p.border
            Rectangle { width: slider.visualPosition * parent.width; height: parent.height; radius: 2; color: root.p.accent }
        }
        handle: Rectangle {
            x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
            y: slider.topPadding + slider.availableHeight / 2 - height / 2
            width: slider.pressed || slider.visualFocus ? 16 : 12; height: width; radius: width / 2
            color: root.p.accent
            border.color: slider.visualFocus ? root.p.text : root.p.accent
            border.width: slider.visualFocus ? 2 : 0
        }
    }

    background: Item {
        Rectangle { anchors.fill: parent; color: root.p.bg }
        Image {
            anchors.fill: parent
            source: root.backend.artworkBase + (root.light ? "backdrop-light.png" : "backdrop-dark.png")
            fillMode: Image.PreserveAspectCrop
            opacity: root.light ? 0.66 : 0.68
            asynchronous: false
        }
        Rectangle { anchors.fill: parent; color: root.light ? "#36eaf0f8" : "#65080c19" }
        // CRT treatment is strictly opt-in and never animates on its own.
        Rectangle {
            anchors.fill: parent
            visible: root.backend.motionEnabled && !root.light
            opacity: 0.16
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#00000000" }
                GradientStop { position: 0.5; color: "#2a7fe9f4" }
                GradientStop { position: 1.0; color: "#00000000" }
            }
        }
    }

    RowLayout {
        x: root.gutter + 10; y: 20; width: root.width - root.gutter * 2 - 20; height: 46
        spacing: 14
        Micro { text: "LOCAL / AUDIO"; color: root.p.signal }
        Rectangle { width: 32; height: 1; color: root.p.border }
        Copy { text: "A quieter place to listen."; color: root.p.dim; font.pixelSize: 13; Layout.fillWidth: true }
        QuietButton {
            objectName: "motionButton"
            text: root.backend.motionEnabled ? "Motion on" : "Motion off"
            checked: root.backend.motionEnabled
            Accessible.name: "Toggle gentle motion and CRT styling"
            ToolTip.text: "Optional. Adds a faint CRT glow and slow reflection drift. Nothing animates until you turn this on."
            onClicked: root.backend.setMotion(!root.backend.motionEnabled)
        }
        QuietButton { objectName: "themeButton"; text: root.light ? "Dark theme" : "Light theme"; onClicked: root.backend.toggleTheme() }
    }

    Glass {
        id: navigation
        objectName: "navigationCard"
        x: root.gutter; y: 86; width: root.navWidth; height: root.height - 250
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 18; spacing: 6
            // Elide the wordmark to the card width: a display serif at 60px otherwise
            // reports a larger implicit width and stretches the whole column.
            Copy { text: "lain."; font.family: "Georgia"; font.pixelSize: root.navWidth > 180 ? 60 : 52; font.letterSpacing: -3; Layout.fillWidth: true; Layout.topMargin: 4 }
            Micro { text: "PERSONAL FREQUENCY"; font.pixelSize: 9; font.letterSpacing: 1.0; Layout.fillWidth: true; Layout.bottomMargin: 16 }
            Micro { text: "EXPLORE"; color: root.p.signal; Layout.fillWidth: true; Layout.bottomMargin: 7 }
            QuietButton { objectName: "libraryNav"; text: "All music"; Layout.fillWidth: true; checked: root.backend.activeView === "library"; onClicked: root.backend.selectView("library") }
            QuietButton { objectName: "favoritesNav"; text: "Favorites"; Layout.fillWidth: true; checked: root.backend.activeView === "favorites"; onClicked: root.backend.selectView("favorites") }
            Micro { text: "PLAYLISTS"; Layout.fillWidth: true; Layout.topMargin: 12; Layout.bottomMargin: 4 }
            ScrollView {
                Layout.fillWidth: true; Layout.preferredHeight: Math.min(112, playlistsColumn.implicitHeight)
                clip: true
                Column {
                    id: playlistsColumn; width: parent.width
                    Repeater {
                        model: root.backend.playlists
                        QuietButton {
                            required property var modelData
                            objectName: "playlist-" + modelData.name
                            width: playlistsColumn.width
                            text: modelData.name; checked: root.backend.activeView === "playlist:" + modelData.name
                            onClicked: root.backend.selectView("playlist:" + modelData.name)
                        }
                    }
                }
            }
            QuietButton { objectName: "newPlaylistButton"; text: "New playlist"; Layout.fillWidth: true; implicitHeight: 34; onClicked: newPlaylist.open() }
            Item { Layout.fillHeight: true }
            Image { visible: root.height > 820; source: root.backend.artworkBase + "wired-city.png"; Layout.fillWidth: true; Layout.maximumWidth: parent.width; Layout.preferredHeight: 76; fillMode: Image.PreserveAspectCrop; opacity: root.light ? 0.65 : 0.55 }
            Micro { text: "ON THIS DEVICE"; Layout.fillWidth: true; Layout.topMargin: 10 }
            Copy { text: root.backend.trackCount + " tracks"; color: root.p.dim; font.pixelSize: 12; Layout.fillWidth: true }
            QuietButton { objectName: "addFolderButton"; text: "Add folder"; primary: true; Layout.fillWidth: true; onClicked: folderDialog.open() }
        }
    }

    Glass {
        id: library
        objectName: "libraryCard"
        x: navigation.x + navigation.width + 18; y: navigation.y
        width: root.width - x - root.artWidth - root.gutter - 18; height: navigation.height
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 24; spacing: 14
            Micro { text: "YOUR COLLECTION"; color: root.p.signal; Layout.fillWidth: true }
            RowLayout {
                Layout.fillWidth: true
                Copy { text: root.backend.viewTitle; font.pixelSize: 26; font.weight: Font.DemiBold; Layout.fillWidth: true }
                QuietButton { objectName: "addFilesButton"; text: "Add files"; onClicked: fileDialog.open() }
            }
            TextField {
                id: search
                objectName: "searchField"
                Layout.fillWidth: true; Layout.preferredHeight: 44
                Accessible.name: "Search music"
                placeholderText: "Search title, artist or album"
                text: root.backend.searchText
                color: root.p.text; placeholderTextColor: root.p.dim
                selectionColor: root.p.accent; selectedTextColor: root.p.bg
                leftPadding: 14; rightPadding: 14
                onTextEdited: root.backend.setSearch(text)
                background: Rectangle { color: root.light ? "#95ffffff" : "#600b1222"; radius: 11; border.width: search.activeFocus ? 2 : 1; border.color: search.activeFocus ? root.p.accent : root.p.border }
            }
            RowLayout {
                Layout.fillWidth: true
                Copy { text: "Album"; color: root.p.dim; font.pixelSize: 12 }
                Select { objectName: "albumFilter"; Layout.fillWidth: true; model: root.albumOptions; Accessible.name: "Filter by album"; onActivated: root.backend.setSearch(currentIndex === 0 ? "" : currentText) }
            }
            Rectangle {
                objectName: "errorBanner"; visible: root.backend.errorText.length > 0
                Layout.fillWidth: true; implicitHeight: 54; radius: 10; color: root.light ? "#f3dde1" : "#48242e"
                RowLayout {
                    anchors.fill: parent; anchors.margins: 8
                    Copy { text: root.backend.errorText; color: root.p.error; Layout.fillWidth: true; wrapMode: Text.WordWrap; maximumLineCount: 2; font.pixelSize: 12; Accessible.role: Accessible.AlertMessage; Accessible.name: text }
                    QuietButton { objectName: "clearErrorButton"; text: "Dismiss"; onClicked: root.backend.clearError() }
                }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 14
                Micro { text: "TRACK / ARTIST"; Layout.fillWidth: true }
                Micro { text: "TIME" }
            }
            Item {
                Layout.fillWidth: true; Layout.fillHeight: true
                ListView {
                    id: trackList; objectName: "trackList"; anchors.fill: parent
                    model: root.backend.tracks; clip: true; spacing: 4
                    ScrollBar.vertical: ScrollBar { }
                    delegate: Rectangle {
                        id: trackRow
                        required property var modelData
                        width: trackList.width; height: 68; radius: 10
                        color: root.backend.currentTrack.id === modelData.id ? (root.light ? "#d8e5e9" : "#402d5260") : "transparent"
                        RowLayout {
                            anchors.fill: parent; anchors.margins: 4; spacing: 4
                            QuietButton {
                                id: trackPlay
                                objectName: "trackPlay-" + trackRow.modelData.id
                                Layout.fillWidth: true; Layout.fillHeight: true
                                Accessible.name: "Play " + trackRow.modelData.title + " by " + trackRow.modelData.artist
                                ToolTip.text: trackRow.modelData.title + " / " + trackRow.modelData.artist + " / " + trackRow.modelData.album
                                contentItem: ColumnLayout {
                                    spacing: 4
                                    Copy { text: trackRow.modelData.title; Layout.fillWidth: true; color: root.backend.currentTrack.id === trackRow.modelData.id ? root.p.signal : root.p.text; font.weight: Font.DemiBold }
                                    Copy { text: trackRow.modelData.artist + " / " + trackRow.modelData.album; color: root.p.dim; Layout.fillWidth: true; font.pixelSize: 12 }
                                }
                                onClicked: root.backend.playTrack(trackRow.modelData.id)
                            }
                            Micro { text: trackRow.modelData.durationText; color: root.p.faint; font.letterSpacing: 0; Layout.preferredWidth: 36 }
                            QuietButton { objectName: "favorite-" + trackRow.modelData.id; text: trackRow.modelData.favorite ? "Saved" : "Save"; implicitWidth: 48; checked: trackRow.modelData.favorite; Accessible.name: "Favorite " + trackRow.modelData.title; onClicked: root.backend.toggleFavorite(trackRow.modelData.id) }
                            QuietButton { objectName: "trackActions-" + trackRow.modelData.id; text: "···"; Accessible.name: "Track actions for " + trackRow.modelData.title; implicitWidth: 36; onClicked: { root.actionTrack = trackRow.modelData; trackActions.open() } }
                        }
                    }
                }
                Column {
                    objectName: "emptyLibrary"
                    anchors.centerIn: parent; width: parent.width
                    visible: trackList.count === 0
                    spacing: 16
                    Copy { text: root.backend.trackCount === 0 ? "Begin with a folder." : "Nothing in this view yet."; width: parent.width; horizontalAlignment: Text.AlignHCenter; font.family: "Georgia"; font.pixelSize: 26 }
                    Copy { text: root.backend.trackCount === 0 ? "Bring your own music. It stays on your device." : "Try another search or collection."; width: parent.width; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter; color: root.p.dim; font.pixelSize: 13 }
                    QuietButton { text: "Add folder"; primary: true; anchors.horizontalCenter: parent.horizontalCenter; onClicked: folderDialog.open() }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Copy { text: root.backend.statusText; color: root.p.dim; font.pixelSize: 12; Layout.fillWidth: true }
                QuietButton { objectName: "cancelScanButton"; text: "Cancel scan"; visible: root.backend.scanBusy; implicitHeight: 32; onClicked: root.backend.cancelScan() }
            }
        }
    }

    Glass {
        id: listening
        objectName: "listeningCard"
        x: root.width - root.gutter - width; y: navigation.y
        width: root.artWidth; height: navigation.height
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 18; spacing: 6
            RowLayout { Layout.fillWidth: true; Micro { text: "OPERATE"; color: root.p.signal; Layout.fillWidth: true } Micro { text: root.backend.playing ? "PLAYING" : root.hasTrack ? "PAUSED" : "STANDBY" } }
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: root.height < 800 ? 154 : 236
                Layout.minimumHeight: 110
                Image { id: portrait; objectName: "portrait"; readonly property bool imageReady: status === Image.Ready; anchors.fill: parent; source: root.hasTrack && root.backend.currentTrack.coverUrl ? root.backend.currentTrack.coverUrl : root.backend.artworkBase + "lain.png"; fillMode: Image.PreserveAspectCrop; clip: true }
                Rectangle { anchors.fill: parent; color: "transparent"; border.color: root.light ? "#22000000" : "#30ffffff"; border.width: 1 }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 60; gradient: Gradient { GradientStop { position: 0; color: "transparent" } GradientStop { position: 1; color: root.light ? "#40f4f6fa" : "#90111829" } } }
            }
            Image { objectName: "reflection"; readonly property bool imageReady: status === Image.Ready; source: root.backend.artworkBase + "lain-reflection.png"; Layout.fillWidth: true; Layout.preferredHeight: root.height < 800 ? 22 : 36; fillMode: Image.PreserveAspectCrop; opacity: root.light ? 0.17 : 0.28 }
            Copy { objectName: "nowTitle"; text: root.hasTrack ? root.backend.currentTrack.title : "Nothing playing"; Layout.fillWidth: true; font.pixelSize: 21; font.weight: Font.DemiBold }
            Copy { text: root.hasTrack ? root.backend.currentTrack.artist : "Choose a track to find your frequency."; Layout.fillWidth: true; font.pixelSize: 12; color: root.p.dim }
            RowLayout {
                Layout.fillWidth: true
                Micro { text: root.hasTrack ? (root.backend.currentTrack.format + " / " + root.backend.currentTrack.sampleRate + " Hz") : "LOCAL / PRIVATE"; font.letterSpacing: 0; Layout.fillWidth: true }
                QuietButton { objectName: "revealButton"; text: "Show file"; enabled: root.hasTrack; implicitHeight: 32; onClicked: root.backend.revealCurrent() }
            }
            Micro { text: "QUEUE / " + root.backend.queue.length; color: root.p.signal; Layout.topMargin: 6 }
            RowLayout {
                Layout.fillWidth: true
                Micro { text: "SIGNAL / AMPLITUDE"; color: root.p.dim; Layout.fillWidth: true }
                Micro { text: root.backend.playing ? "LIVE PCM" : "SILENT"; color: root.p.dim }
            }
            Item {
                id: amplitude; objectName: "amplitudeMeter"
                Layout.fillWidth: true; Layout.preferredHeight: 26
                Row {
                    anchors.fill: parent; spacing: 2
                    Repeater {
                        model: 24
                        Item {
                            width: (amplitude.width - 46) / 24; height: amplitude.height
                            Rectangle {
                                anchors.bottom: parent.bottom; width: parent.width; radius: 1
                                height: Math.max(1, parent.height * (root.backend.levels[index] || 0))
                                color: root.p.signal
                                opacity: root.backend.playing ? 0.85 : 0.28
                                Accessible.role: Accessible.Indicator
                                Accessible.name: "Amplitude bar " + (index + 1)
                            }
                        }
                    }
                }
            }
            Field { id: queueSearch; objectName: "queueSearch"; visible: root.backend.queue.length > 0; Layout.fillWidth: true; implicitHeight: 32; placeholderText: "Filter queue"; Accessible.name: "Filter queue" }
            ListView {
                id: queueList; objectName: "queueList"
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 44
                model: root.backend.queue.filter(t => (t.title + " " + t.artist).toLowerCase().includes(queueSearch.text.toLowerCase())); clip: true; spacing: 2
                ScrollBar.vertical: ScrollBar { }
                delegate: QuietButton {
                    id: queueRow
                    required property var modelData
                    required property int index
                    objectName: "queuePlay-" + modelData.id
                    width: queueList.width; height: 44
                    readonly property int originalIndex: root.backend.queue.findIndex(t => t.id === modelData.id)
                    checked: originalIndex === root.backend.queueIndex
                    Accessible.name: "Play queued " + modelData.title
                    contentItem: RowLayout {
                        spacing: 10
                        Micro { text: queueRow.checked ? "NOW" : String(queueRow.originalIndex + 1).padStart(2, "0"); color: queueRow.checked ? root.p.signal : root.p.dim; font.letterSpacing: 0; Layout.preferredWidth: 30 }
                        Copy { text: queueRow.modelData.title; Layout.fillWidth: true; font.pixelSize: 12 }
                        Micro { text: queueRow.modelData.durationText; font.letterSpacing: 0 }
                    }
                    onClicked: root.backend.playQueued(originalIndex)
                }
            }
            Copy { visible: root.backend.queue.length === 0; text: "Your queue appears when you play music."; Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 12; color: root.p.dim; Layout.bottomMargin: 10 }
        }
    }

    Glass {
        id: transport
        objectName: "transportCard"
        x: root.gutter; y: root.height - 140; width: root.width - root.gutter * 2; height: 116
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 18; spacing: 3
            RowLayout {
                Layout.fillWidth: true; spacing: 14
                Micro { text: root.backend.positionText; color: root.p.faint; Layout.preferredWidth: 45 }
                MeterSlider { objectName: "timeline"; stepSize: 1000; Layout.fillWidth: true; from: 0; to: Math.max(1, root.backend.durationMs); value: root.backend.positionMs; enabled: root.hasTrack && root.backend.seekable; Accessible.name: "Playback position"; onReported: root.backend.seek(Math.round(reportedValue)) }
                Micro { text: root.backend.durationText; color: root.p.faint; Layout.preferredWidth: 45; horizontalAlignment: Text.AlignRight }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                Copy { text: root.hasTrack ? root.backend.currentTrack.title : "Local music. No distractions."; color: root.p.dim; Layout.preferredWidth: root.compact ? 166 : 250; font.pixelSize: 12 }
                Item { Layout.fillWidth: true }
                QuietButton { objectName: "shuffleButton"; text: "Shuffle"; checked: root.backend.shuffle; onClicked: root.backend.toggleShuffle() }
                QuietButton { objectName: "previousButton"; text: "Previous"; enabled: root.hasTrack; onClicked: root.backend.previousTrack() }
                QuietButton { objectName: "playButton"; text: root.backend.playing ? "Pause" : "Play"; primary: true; enabled: root.hasTrack; implicitWidth: 76; onClicked: root.backend.togglePlayback() }
                QuietButton { objectName: "nextButton"; text: "Next"; enabled: root.hasTrack; onClicked: root.backend.nextTrack() }
                QuietButton { objectName: "repeatButton"; text: root.backend.repeatMode === "off" ? "Repeat" : root.backend.repeatMode === "one" ? "Repeat one" : "Repeat all"; checked: root.backend.repeatMode !== "off"; onClicked: root.backend.cycleRepeat() }
                Item { Layout.fillWidth: true }
                QuietButton { objectName: "muteButton"; text: root.backend.muted ? "Unmute" : "Mute"; onClicked: root.backend.toggleMute() }
                MeterSlider { objectName: "volumeSlider"; stepSize: 0.02; Layout.preferredWidth: root.compact ? 88 : 120; from: 0; to: 1; value: root.backend.volume; Accessible.name: "Volume"; onReported: root.backend.setVolume(reportedValue) }
            }
        }
    }

    FolderDialog { id: folderDialog; objectName: "folderDialog"; title: "Add a music folder"; onAccepted: root.backend.addFolder(selectedFolder) }
    Dialog {
        id: trackActions
        objectName: "trackActionsDialog"
        anchors.centerIn: parent; width: 380; modal: true; padding: 24
        title: "Track actions"
        background: Rectangle { color: root.light ? "#f4f6fa" : "#141e30"; radius: 18; border.color: root.p.border }
        contentItem: ColumnLayout {
            spacing: 16
            Copy { text: root.actionTrack.title || ""; Layout.fillWidth: true; font.weight: Font.DemiBold }
            Copy { text: "Add to playlist"; color: root.p.dim }
            Select {
                id: playlistChoice; objectName: "playlistChoice"
                Layout.fillWidth: true; model: root.backend.playlists; textRole: "name"
                Accessible.name: "Choose a playlist"
            }
            QuietButton { objectName: "addToPlaylistButton"; text: "Add to playlist"; primary: true; enabled: playlistChoice.count > 0; Layout.fillWidth: true; onClicked: { root.backend.addToPlaylist(playlistChoice.currentText, root.actionTrack.id); trackActions.close() } }
            Copy { text: "Remove only from this library. Your file stays safe."; color: root.p.dim; Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 12 }
            QuietButton { objectName: "removeTrackButton"; text: "Remove from library"; Layout.fillWidth: true; onClicked: { root.backend.removeFromLibrary(root.actionTrack.id); trackActions.close() } }
            QuietButton { text: "Close"; Layout.fillWidth: true; onClicked: trackActions.close() }
        }
    }
    Dialog {
        id: newPlaylist
        objectName: "newPlaylistDialog"
        anchors.centerIn: parent; width: 360; modal: true; padding: 24
        title: "New playlist"
        onOpened: { playlistName.text = ""; playlistName.forceActiveFocus(Qt.PopupFocusReason) }
        background: Rectangle { color: root.light ? "#f4f6fa" : "#141e30"; radius: 18; border.color: root.p.border }
        contentItem: ColumnLayout {
            spacing: 16
            Copy { text: "Playlist name" }
            Field { id: playlistName; objectName: "playlistNameField"; Layout.fillWidth: true; placeholderText: "e.g. Late-night listening"; maximumLength: 80; Accessible.name: "Playlist name"; onAccepted: if (text.trim().length > 0) { root.backend.createPlaylist(text.trim()); newPlaylist.close() } }
            QuietButton { objectName: "createPlaylistButton"; text: "Create playlist"; primary: true; enabled: playlistName.text.trim().length > 0; Layout.fillWidth: true; onClicked: { root.backend.createPlaylist(playlistName.text.trim()); newPlaylist.close() } }
            QuietButton { text: "Cancel"; Layout.fillWidth: true; onClicked: newPlaylist.close() }
        }
    }
    FileDialog { id: fileDialog; objectName: "fileDialog"; title: "Add music files"; fileMode: FileDialog.OpenFiles; nameFilters: ["Audio (*.mp3 *.flac *.wav *.ogg *.opus *.m4a *.aac *.wma *.aiff *.alac)", "All files (*)"]; onAccepted: root.backend.addFiles(selectedFiles) }
}
