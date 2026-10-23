import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: dialog
    objectName: "installExplorerDialog"
    required property QtObject controller
    property string status: ""
    property string statusDetails: ""
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
            objectName: "explorerStatus"
            Layout.fillWidth: true
            text: dialog.status
            HoverHandler { id: statusHover }
            ToolTip.visible: statusHover.hovered
            ToolTip.text: dialog.statusDetails
            wrapMode: Text.WordWrap
        }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            Button {
                objectName: "installExplorer"
                text: qsTr("Install")
                ToolTip.visible: hovered || activeFocus
                ToolTip.text: qsTr("Add Open in FolderConformer to right-click menus for folders, folder backgrounds, and drives.")
                enabled: !dialog.controller.running && !dialog.controller.updates.busy
                onClicked: {
                    dialog.status = qsTr("Installing…")
                    dialog.statusDetails = ""
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
            dialog.status = code === 0 ? qsTr("Installed in File Explorer") : qsTr("Failed")
            dialog.statusDetails = code === 0 ? "" : qsTr("Process exited with code %1. See log.").arg(code)
        }
    }
}
