import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

GroupBox {
    id: panel
    objectName: "ruleFoldersPanel"
    required property QtObject controller
    property bool choosing: false
    title: qsTr("Folders")
    contentHeight: foldersContent.implicitHeight
    contentWidth: foldersContent.implicitWidth

    ColumnLayout {
        id: foldersContent
        anchors.fill: parent
        spacing: 8
        Label { text: qsTr("Landscape folder name") }
        TextField {
            objectName: "landscapeFolder"
            Layout.fillWidth: true
            text: panel.controller.landscapeFolder
            Accessible.name: qsTr("Landscape folder name")
            validator: RegularExpressionValidator { regularExpression: /[^<>:"/\\|?*.][^<>:"/\\|?*]*/ }
            onTextEdited: panel.controller.landscapeFolder = text
        }
        Label { text: qsTr("User configuration folder") }
        RowLayout {
            Layout.fillWidth: true
            TextField {
                id: configFolder
                objectName: "configFolder"
                Layout.fillWidth: true
                text: panel.controller.configFolder
                Accessible.name: qsTr("User configuration folder")
                onEditingFinished: panel.controller.configFolder = text
            }
            Button {
                objectName: "browseConfigFolder"
                text: qsTr("Browse…")
                onClicked: panel.choosing = true
            }
            Button {
                objectName: "openConfigFolder"
                text: qsTr("Open")
                onClicked: panel.controller.openConfigFolder()
            }
        }
        Label { text: qsTr("Video folder") }
        TextField {
            objectName: "videoFolder"
            Layout.fillWidth: true
            text: panel.controller.videoFolder
            Accessible.name: qsTr("Video folder")
            onTextEdited: panel.controller.videoFolder = text
        }
        Label { text: qsTr("Image folder") }
        TextField {
            objectName: "imageFolder"
            Layout.fillWidth: true
            text: panel.controller.imageFolder
            Accessible.name: qsTr("Image folder")
            onTextEdited: panel.controller.imageFolder = text
        }
    }
    Loader {
        active: panel.choosing
        sourceComponent: Component {
            FolderDialog {
                title: qsTr("Select user configuration folder")
                Component.onCompleted: open()
                onAccepted: {
                    panel.controller.selectConfigFolder(selectedFolder)
                    panel.choosing = false
                }
                onRejected: panel.choosing = false
            }
        }
    }
}
