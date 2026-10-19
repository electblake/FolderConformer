import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: dialog
    objectName: "extras"
    required property QtObject controller
    property string status: ""
    title: qsTr("Extras")
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
        GroupBox {
            title: qsTr("File Explorer")
            Layout.fillWidth: true
            ColumnLayout {
                anchors.fill: parent
                Label {
                    Layout.fillWidth: true
                    text: qsTr("Add Open in FolderConformer to right-click menus for folders, folder backgrounds, and drives.")
                    wrapMode: Text.WordWrap
                }
                Button {
                    objectName: "installExplorer"
                    text: qsTr("Install in File Explorer")
                    enabled: !dialog.controller.running && !dialog.controller.updates.busy
                    onClicked: {
                        dialog.status = qsTr("Installing…")
                        dialog.controller.installExplorer()
                    }
                }
            }
        }
        Label {
            objectName: "explorerStatus"
            Layout.fillWidth: true
            text: dialog.status
            wrapMode: Text.WordWrap
        }
        Button {
            objectName: "closeExtras"
            Layout.alignment: Qt.AlignRight
            text: qsTr("Close")
            enabled: !dialog.controller.running
            onClicked: dialog.close()
        }
    }
    Connections {
        target: dialog.controller
        function onExplorerCompleted(code) {
            dialog.status = code === 0 ? qsTr("Installed in File Explorer") : qsTr("Process exited with code %1. See log.").arg(code)
        }
    }
}
