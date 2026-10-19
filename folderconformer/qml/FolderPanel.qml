import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

GroupBox {
    id: panel
    required property QtObject controller
    property bool choosing: false
    title: qsTr("Input folder")
    contentHeight: folderContent.implicitHeight
    contentWidth: folderContent.implicitWidth

    ColumnLayout {
        id: folderContent
        anchors.fill: parent
        RowLayout {
            Layout.fillWidth: true
            TextField {
                objectName: "inputFolder"
                Layout.fillWidth: true
                text: panel.controller.folder
                Accessible.name: qsTr("Input folder path")
                onTextEdited: panel.controller.folder = text
            }
            Button {
                text: qsTr("Browse…")
                onClicked: panel.choosing = true
            }
        }
        CheckBox {
            objectName: "includeSubdirectories"
            text: qsTr("Include subdirectories")
            checked: panel.controller.includeSubdirectories
            onToggled: panel.controller.includeSubdirectories = checked
        }
    }
    Loader {
        active: panel.choosing
        sourceComponent: Component {
            FolderDialog {
                title: qsTr("Select input folder")
                Component.onCompleted: open()
                onAccepted: {
                    panel.controller.selectFolder(selectedFolder)
                    panel.choosing = false
                }
                onRejected: panel.choosing = false
            }
        }
    }
}
