pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

GroupBox {
    id: panel
    objectName: "rulesPanel"
    required property QtObject controller
    signal runOnceRequested(int index)
    title: qsTr("Rules — applied from top to bottom")
    contentWidth: ruleContents.implicitWidth
    contentHeight: ruleContents.implicitHeight

    ColumnLayout {
        id: ruleContents
        anchors.fill: parent
        spacing: 8
        Repeater {
            model: panel.controller.rules
            delegate: RowLayout {
                id: ruleRow
                required property int index
                required property var modelData
                Layout.fillWidth: true
                Label {
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
                        data_extensions: "R3"
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
                        data_extensions: qsTr("other")
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
                        remove_empty_dirs: qsTr("Remove empty dirs")
                    })[ruleRow.modelData.id]
                    checked: ruleRow.modelData.enabled
                    onToggled: panel.controller.setEnabled(ruleRow.index, checked)
                }
                Button {
                    objectName: ruleRow.modelData.id + "Check"
                    text: qsTr("Check")
                    enabled: !panel.controller.running && panel.controller.folder.length > 0
                    onClicked: panel.controller.checkRule(ruleRow.modelData.id)
                }
                Button {
                    objectName: ruleRow.modelData.id + "RunOnce"
                    text: qsTr("Run Once")
                    enabled: !panel.controller.running && panel.controller.folder.length > 0
                        && ((ruleRow.modelData.id !== "landscape" && ruleRow.modelData.id !== "landscape_images")
                            || panel.controller.landscapeFolder.length > 0)
                    onClicked: panel.runOnceRequested(ruleRow.index)
                }
                Button {
                    objectName: ruleRow.modelData.id + "MoveUp"
                    text: qsTr("Move up")
                    enabled: ruleRow.index > 0
                    onClicked: panel.controller.moveRule(ruleRow.index, -1)
                }
                Button {
                    objectName: ruleRow.modelData.id + "MoveDown"
                    text: qsTr("Move down")
                    enabled: ruleRow.index < panel.controller.rules.length - 1
                    onClicked: panel.controller.moveRule(ruleRow.index, 1)
                }
            }
        }
    }
}
