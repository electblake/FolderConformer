import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: dialog
    objectName: "softwareUpdate"
    required property QtObject updater
    signal installRequested()
    title: qsTr("Software Update")
    flags: Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
    modality: Qt.WindowModal
    minimumWidth: Math.max(460, content.implicitWidth + 32)
    width: Math.max(520, minimumWidth)
    height: content.implicitHeight + 32
    minimumHeight: content.implicitHeight + 32
    onClosing: function(close) { close.accepted = !dialog.updater.busy }

    Shortcut {
        sequence: "Escape"
        onActivated: { if (!dialog.updater.busy) dialog.close() }
    }

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        GroupBox {
            title: qsTr("Updates")
            Layout.fillWidth: true
            ColumnLayout {
                anchors.fill: parent
                Label {
                    Layout.fillWidth: true
                    text: dialog.updater.versions
                    wrapMode: Text.WordWrap
                }
                RowLayout {
                    Button {
                        objectName: "checkForUpdates"
                        text: qsTr("Check for Updates")
                        enabled: !dialog.updater.busy
                        onClicked: dialog.updater.check()
                    }
                    Button {
                        objectName: "viewReleases"
                        text: qsTr("View Releases")
                        ToolTip.visible: hovered || activeFocus
                        ToolTip.text: dialog.updater.releaseInfo
                        enabled: !dialog.updater.busy
                        onClicked: Qt.openUrlExternally(dialog.updater.releasesUrl)
                    }
                    Button {
                        objectName: "downloadUpdate"
                        text: qsTr("Download Update")
                        enabled: !dialog.updater.busy && dialog.updater.available && !dialog.updater.ready
                        onClicked: dialog.updater.download()
                    }
                    Button {
                        objectName: "installUpdate"
                        text: qsTr("Quit and Install")
                        ToolTip.visible: hovered || activeFocus
                        ToolTip.text: qsTr("Quit and install when ready.")
                        enabled: !dialog.updater.busy && dialog.updater.ready
                        onClicked: dialog.installRequested()
                    }
                }
            }
        }
        Label {
            objectName: "updateStatus"
            Layout.fillWidth: true
            text: dialog.updater.status
            wrapMode: Text.WordWrap
        }
        ProgressBar {
            objectName: "updateProgress"
            Layout.fillWidth: true
            indeterminate: dialog.updater.indeterminate
            from: 0
            to: 1000
            value: dialog.updater.progress
            Accessible.name: qsTr("Update progress")
        }
        Button {
            objectName: "closeUpdate"
            Layout.alignment: Qt.AlignRight
            text: qsTr("Close")
            enabled: !dialog.updater.busy
            onClicked: dialog.close()
        }
    }
}
