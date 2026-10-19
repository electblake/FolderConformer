import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

GroupBox {
    id: panel
    objectName: "filesPanel"
    required property QtObject controller
    title: qsTr("Files")

    ColumnLayout {
        anchors.fill: parent
        spacing: 8
        Label { text: qsTr("Video file extensions (separated by semicolons)") }
        TextField {
            objectName: "videoExtensions"
            Layout.fillWidth: true
            text: panel.controller.videoExtensions
            Accessible.name: qsTr("Video file extensions")
            onTextEdited: panel.controller.videoExtensions = text
        }
        Label { text: qsTr("Image file extensions (separated by semicolons)") }
        TextField {
            objectName: "imageExtensions"
            Layout.fillWidth: true
            text: panel.controller.imageExtensions
            Accessible.name: qsTr("Image file extensions")
            onTextEdited: panel.controller.imageExtensions = text
        }
    }
}
