import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: dialog
    objectName: "installExplorerDialog"
    required property QtObject controller
    property string status: ""
    title: qsTr("Install for File Explorer")
    flags: Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
    modality: Qt.WindowModal
    width: 520
    minimumWidth: 460
    height: content.implicitHeight + 32
    minimumHeight: content.implicitHeight + 32
    onClosing: function(close) { close.accepted = !dialog.controller.running }

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12
        Label {
            Layout.fillWidth: true
            text: qsTr("Add Open in FolderConformer to right-click menus for folders, folder backgrounds, and drives.")
            wrapMode: Text.WordWrap
        }
        Label {
            objectName: "explorerStatus"
            Layout.fillWidth: true
            text: dialog.status
            wrapMode: Text.WordWrap
        }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            Button {
                objectName: "installExplorer"
                text: qsTr("Install")
                enabled: !dialog.controller.running && !dialog.controller.updates.busy
                onClicked: {
                    dialog.status = qsTr("Installing…")
                    dialog.controller.installExplorer()
                }
            }
            Button {
                objectName: "closeInstallExplorer"
                text: qsTr("Close")
                enabled: !dialog.controller.running
                onClicked: dialog.close()
            }
        }
    }
    Connections {
        target: dialog.controller
        function onExplorerCompleted(code) {
            dialog.status = code === 0 ? qsTr("Installed in File Explorer") : qsTr("Process exited with code %1. See log.").arg(code)
        }
    }
}
