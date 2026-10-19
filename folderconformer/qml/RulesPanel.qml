import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

GroupBox {
    id: panel
    objectName: "rulesPanel"
    required property QtObject controller
    title: qsTr("Rules — applied from top to bottom")

    ColumnLayout {
        anchors.fill: parent
        spacing: 8
        Repeater {
            model: panel.controller.rules
            delegate: RowLayout {
                id: ruleRow
                required property int index
                required property var modelData
                Layout.fillWidth: true
                Rectangle {
                    Layout.preferredWidth: 64
                    implicitHeight: ruleType.implicitHeight + 8
                    radius: height / 2
                    color: panel.palette.alternateBase
                    border.color: panel.palette.mid
                    Label {
                        id: ruleType
                        anchors.centerIn: parent
                        text: ruleRow.modelData.id === "landscape" || ruleRow.modelData.id === "extension"
                            ? qsTr("file") : qsTr("folder")
                    }
                }
                CheckBox {
                    objectName: ruleRow.modelData.id + "Enabled"
                    Layout.fillWidth: true
                    text: ({
                        landscape: qsTr("Landscape and square media (ratio ≥ 1)"),
                        extension: qsTr("Group all files by extension"),
                        rename_images: qsTr("Rename image / images folders to %1").arg(panel.controller.imageFolder),
                        rename_videos: qsTr("Rename video / videos folders to %1").arg(panel.controller.videoFolder),
                        photo_extensions: qsTr("Move image extension folders into %1").arg(panel.controller.imageFolder),
                        video_extensions: qsTr("Move video extension folders into %1").arg(panel.controller.videoFolder)
                    })[ruleRow.modelData.id]
                    checked: ruleRow.modelData.enabled
                    onToggled: panel.controller.setEnabled(ruleRow.index, checked)
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
        Label {
            Layout.fillWidth: true
            text: qsTr("File rules add destination subfolders. Folder rules rename or move existing folders in sequence. Folder names match without regard to case.")
            wrapMode: Text.WordWrap
        }
    }
}
