import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: dialog
    objectName: "conformingCompleteDialog"
    required property QtObject controller
    signal quitRequested()
    title: qsTr("Conforming Complete")
    flags: Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
    modality: Qt.WindowModal
    width: content.implicitWidth + 48
    minimumWidth: content.implicitWidth + 48
    height: content.implicitHeight + 48
    minimumHeight: content.implicitHeight + 48
    onVisibleChanged: {
        if (visible)
            closeButton.forceActiveFocus()
    }

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: 24
        spacing: 28
        Label {
            Layout.fillWidth: true
            text: qsTr("All conform rules have completed. Check the activity log for details.")
            horizontalAlignment: Text.AlignHCenter
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Button {
                objectName: "completionOpenFolder"
                Layout.fillWidth: true
                text: qsTr("Open Folder")
                onClicked: dialog.controller.openOutputFolder()
            }
            Button {
                objectName: "completionOpenFolderAndQuit"
                Layout.fillWidth: true
                text: qsTr("Open Folder and Quit")
                onClicked: {
                    dialog.controller.openOutputFolder()
                    dialog.quitRequested()
                }
            }
            Button {
                objectName: "completionQuit"
                Layout.fillWidth: true
                text: qsTr("Quit")
                onClicked: dialog.quitRequested()
            }
            Button {
                id: closeButton
                objectName: "completionClose"
                Layout.fillWidth: true
                text: qsTr("Close")
                onClicked: dialog.close()
            }
        }
    }
}
