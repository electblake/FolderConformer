pragma ComponentBehavior: Bound

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

    RowLayout {
        id: folderContent
        anchors.fill: parent
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
