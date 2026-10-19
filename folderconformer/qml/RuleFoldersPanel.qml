import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

GroupBox {
    id: panel
    objectName: "ruleFoldersPanel"
    required property QtObject controller
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
}
