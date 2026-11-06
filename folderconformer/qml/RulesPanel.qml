pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

GroupBox {
    id: panel
    objectName: "rulesPanel"
    required property QtObject controller
    signal runOnceRequested(int index)
    signal settingsRequested(string ruleId)
    title: qsTr("Rules")
    hoverEnabled: true
    ToolTip.visible: hovered
    ToolTip.text: qsTr("Rules are applied from top to bottom.")
    contentWidth: ruleContents.implicitWidth
    contentHeight: ruleContents.contentHeight

    ListView {
        id: ruleContents
        objectName: "ruleList"
        anchors.fill: parent
        clip: true
        spacing: 8
        cacheBuffer: 4096
        implicitWidth: contentItem.children.reduce((width, item) => Math.max(width, item.implicitWidth), 0)
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        property bool dragOver: false
        property real dragY: 0
        Timer {
            interval: 16
            repeat: true
            running: ruleContents.dragOver
            onTriggered: {
                const direction = ruleContents.dragY < 32 ? -1 : (ruleContents.dragY > ruleContents.height - 32 ? 1 : 0)
                ruleContents.contentY = Math.max(ruleContents.originY,
                    Math.min(ruleContents.originY + Math.max(0, ruleContents.contentHeight - ruleContents.height),
                             ruleContents.contentY + direction * 8))
            }
        }
        model: panel.controller.rules
        delegate: DropArea {
            id: dropRow
            required property int index
            required property var modelData
            width: ruleContents.width
            height: ruleRow.implicitHeight
            implicitWidth: ruleRow.implicitWidth
            keys: ["application/x-folderconformer-rule"]
            property bool insertAfter: false
            function trackDrag(drag) {
                insertAfter = drag.y >= height / 2
                ruleContents.dragY = mapToItem(ruleContents, drag.x, drag.y).y
                ruleContents.dragOver = true
            }
            onPositionChanged: function(drag) { trackDrag(drag) }
            onEntered: function(drag) { trackDrag(drag) }
            onExited: ruleContents.dragOver = false
            onDropped: function(drop) {
                ruleContents.dragOver = false
                const sourceIndex = drop.source.sourceIndex
                const boundary = index + (drop.y >= height / 2 ? 1 : 0)
                const destination = boundary > sourceIndex ? boundary - 1 : boundary
                drop.accept(Qt.MoveAction)
                if (destination !== sourceIndex)
                    Qt.callLater(panel.controller.moveRule, sourceIndex, destination - sourceIndex)
            }
            Rectangle {
                width: parent.width
                height: 2
                y: dropRow.insertAfter ? parent.height + 3 : -4
                color: panel.palette.highlight
                visible: dropRow.containsDrag
                z: 2
            }
            RowLayout {
                id: ruleRow
                readonly property int index: dropRow.index
                readonly property var modelData: dropRow.modelData
                width: parent.width
                Label {
                    id: ruleIdentifier
                    objectName: ruleRow.modelData.id + "Identifier"
                    Layout.preferredWidth: 32
                    text: ({
                        landscape: "H2",
                        extension: "N4",
                        rename_images: "F8",
                        rename_videos: "N2",
                        photo_extensions: "J1",
                        video_extensions: "S6",
                        remove_empty_dirs: "K9",
                        landscape_images: "B7",
                        data_extensions: "R3",
                        music_videos: "M5",
                        flatten_videos: "V1",
                        flatten_images: "I1",
                        non_video_to_root: "V2",
                        non_image_to_root: "I2",
                        create_empty_file: "E1"
                    })[ruleRow.modelData.id]
                }
                Label {
                    objectName: ruleRow.modelData.id + "CheckStatus"
                    Layout.preferredWidth: 40
                    text: panel.controller.checkStatuses[ruleRow.modelData.id] === undefined
                        ? "-" : panel.controller.checkStatuses[ruleRow.modelData.id]
                    Accessible.name: qsTr("Check status")
                }
                Label {
                    objectName: ruleRow.modelData.id + "RuleType"
                    Layout.preferredWidth: 64
                    text: ruleRow.modelData.id === "landscape" || ruleRow.modelData.id === "landscape_images"
                        || ruleRow.modelData.id === "extension" || ruleRow.modelData.id === "photo_extensions"
                        || ruleRow.modelData.id === "video_extensions" || ruleRow.modelData.id === "data_extensions"
                        || ruleRow.modelData.id === "music_videos"
                        || ruleRow.modelData.id === "non_video_to_root" || ruleRow.modelData.id === "non_image_to_root"
                        || ruleRow.modelData.id === "create_empty_file"
                        ? qsTr("file") : qsTr("folder")
                }
                Label {
                    objectName: ruleRow.modelData.id + "MediaType"
                    Layout.preferredWidth: 64
                    text: ({
                        landscape: qsTr("video"),
                        extension: qsTr("other"),
                        rename_images: qsTr("image"),
                        rename_videos: qsTr("video"),
                        photo_extensions: qsTr("image"),
                        video_extensions: qsTr("video"),
                        remove_empty_dirs: qsTr("other"),
                        landscape_images: qsTr("image"),
                        data_extensions: qsTr("other"),
                        music_videos: qsTr("video"),
                        flatten_videos: qsTr("video"),
                        flatten_images: qsTr("image"),
                        non_video_to_root: qsTr("video"),
                        non_image_to_root: qsTr("image"),
                        create_empty_file: qsTr("other")
                    })[ruleRow.modelData.id]
                }
                CheckBox {
                    objectName: ruleRow.modelData.id + "Enabled"
                    Layout.fillWidth: true
                    text: ({
                        landscape: qsTr("Move landscape and square videos"),
                        landscape_images: qsTr("Move landscape and square images"),
                        data_extensions: qsTr("Move data files into Data folder"),
                        extension: qsTr("Group loose files by extension"),
                        rename_images: qsTr("Single images folder"),
                        rename_videos: qsTr("Single videos folder"),
                        photo_extensions: qsTr("Move images into images folder"),
                        video_extensions: qsTr("Move videos into videos folder"),
                        remove_empty_dirs: qsTr("Remove empty dirs"),
                        music_videos: qsTr("Move videos containing music"),
                        flatten_videos: qsTr("Flatten videos folder"),
                        flatten_images: qsTr("Flatten images folder"),
                        non_video_to_root: qsTr("Move non-video files to root"),
                        non_image_to_root: qsTr("Move non-image files to root"),
                        create_empty_file: qsTr("Create empty file")
                    })[ruleRow.modelData.id]
                    checked: ruleRow.modelData.enabled
                    onToggled: panel.controller.setEnabled(ruleRow.index, checked)
                }
                Button {
                    id: ruleSettings
                    objectName: ruleRow.modelData.id + "Settings"
                    Layout.preferredWidth: implicitHeight
                    Accessible.name: qsTr("Settings for %1").arg(ruleIdentifier.text)
                    ToolTip.visible: hovered || activeFocus
                    ToolTip.text: Accessible.name
                    text: "\ue713"
                    font.family: "Segoe Fluent Icons"
                    font.pixelSize: 16
                    onClicked: panel.settingsRequested(ruleIdentifier.text)
                }
                Button {
                    objectName: ruleRow.modelData.id + "Check"
                    text: qsTr("Check")
                    display: AbstractButton.IconOnly
                    icon.source: "image://standard/check"
                    icon.width: 16
                    icon.height: 16
                    icon.color: "transparent"
                    Layout.preferredWidth: implicitHeight
                    Accessible.name: qsTr("Check this rule")
                    ToolTip.visible: hovered || activeFocus
                    ToolTip.text: qsTr("Check this rule")
                    enabled: !panel.controller.running && panel.controller.folder.length > 0
                    onClicked: panel.controller.checkRule(ruleRow.modelData.id)
                }
                Button {
                    objectName: ruleRow.modelData.id + "RunOnce"
                    text: qsTr("Run Once")
                    display: AbstractButton.IconOnly
                    icon.source: "image://standard/run"
                    icon.width: 16
                    icon.height: 16
                    Layout.preferredWidth: implicitHeight
                    Accessible.name: qsTr("Run this rule once")
                    ToolTip.visible: hovered || activeFocus
                    ToolTip.text: qsTr("Run this rule once")
                    enabled: !panel.controller.running && panel.controller.folder.length > 0
                        && ((ruleRow.modelData.id !== "landscape" && ruleRow.modelData.id !== "landscape_images")
                            || panel.controller.landscapeFolder.length > 0)
                    onClicked: panel.runOnceRequested(ruleRow.index)
                }
                Button {
                    objectName: ruleRow.modelData.id + "MoveUp"
                    text: qsTr("Move up")
                    display: AbstractButton.IconOnly
                    icon.source: "image://standard/up"
                    icon.width: 16
                    icon.height: 16
                    Layout.preferredWidth: implicitHeight
                    Accessible.name: qsTr("Move rule up")
                    ToolTip.visible: hovered || activeFocus
                    ToolTip.text: qsTr("Move rule up")
                    enabled: ruleRow.index > 0
                    onClicked: panel.controller.moveRule(ruleRow.index, -1)
                }
                Button {
                    objectName: ruleRow.modelData.id + "MoveDown"
                    text: qsTr("Move down")
                    display: AbstractButton.IconOnly
                    icon.source: "image://standard/down"
                    icon.width: 16
                    icon.height: 16
                    Layout.preferredWidth: implicitHeight
                    Accessible.name: qsTr("Move rule down")
                    ToolTip.visible: hovered || activeFocus
                    ToolTip.text: qsTr("Move rule down")
                    enabled: ruleRow.index < panel.controller.rules.length - 1
                    onClicked: panel.controller.moveRule(ruleRow.index, 1)
                }
                ToolButton {
                    id: moveHandle
                    objectName: ruleRow.modelData.id + "DragHandle"
                    Layout.preferredWidth: implicitHeight
                    text: "\ue759"
                    font.family: "Segoe Fluent Icons"
                    font.pixelSize: 16
                    Accessible.name: qsTr("Drag to reorder %1").arg(ruleIdentifier.text)
                    ToolTip.visible: hovered && !moveDrag.active
                    ToolTip.text: Accessible.name
                    readonly property int sourceIndex: ruleRow.index
                    Rectangle {
                        id: dragProxy
                        parent: panel
                        width: 36
                        height: 36
                        radius: 4
                        z: 10
                        visible: Drag.active
                        color: panel.palette.highlight
                        Drag.keys: ["application/x-folderconformer-rule"]
                        Drag.source: moveHandle
                        Drag.supportedActions: Qt.MoveAction
                        Drag.proposedAction: Qt.MoveAction
                        Drag.hotSpot.x: width / 2
                        Drag.hotSpot.y: height / 2
                        Label {
                            anchors.centerIn: parent
                            text: moveHandle.text
                            font: moveHandle.font
                            color: panel.palette.highlightedText
                        }
                    }
                    Shortcut {
                        sequence: "Escape"
                        enabled: dragProxy.Drag.active
                        onActivated: {
                            dragProxy.Drag.cancel()
                            ruleContents.dragOver = false
                        }
                    }
                    DragHandler {
                        id: moveDrag
                        target: null
                        onCentroidChanged: {
                            if (active) {
                                const point = moveHandle.mapToItem(panel, centroid.position.x, centroid.position.y)
                                dragProxy.x = point.x - dragProxy.width / 2
                                dragProxy.y = point.y - dragProxy.height / 2
                            }
                        }
                        acceptedButtons: Qt.LeftButton
                        cursorShape: active ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                        onActiveChanged: {
                            if (active) {
                                const point = moveHandle.mapToItem(panel, centroid.position.x, centroid.position.y)
                                dragProxy.x = point.x - dragProxy.width / 2
                                dragProxy.y = point.y - dragProxy.height / 2
                                dragProxy.Drag.active = true
                            } else {
                                dragProxy.Drag.drop()
                                ruleContents.dragOver = false
                            }
                        }
                        onCanceled: {
                            dragProxy.Drag.cancel()
                            ruleContents.dragOver = false
                        }
                    }
                }
            }
        }
    }
}
