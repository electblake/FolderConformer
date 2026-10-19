import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Pane {
    id: screen
    objectName: "conformerScreen"
    required property QtObject controller
    property alias choosingFolder: folderPanel.choosing
    property string status: qsTr("Ready")
    property string completionSummary: ""
    property int processed: 0
    property int total: 0

    ColumnLayout {
        anchors.fill: parent
        spacing: 12

        ScrollView {
            id: settingsScroll
            objectName: "settingsScroll"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: 800
            contentWidth: availableWidth
            clip: true
            ColumnLayout {
                width: settingsScroll.availableWidth
                spacing: 12
                FolderPanel {
                    id: folderPanel
                    Layout.fillWidth: true
                    controller: screen.controller
                    enabled: !screen.controller.running
                }
                RulesPanel {
                    Layout.fillWidth: true
                    controller: screen.controller
                    enabled: !screen.controller.running
                }
                RuleFoldersPanel {
                    Layout.fillWidth: true
                    controller: screen.controller
                    enabled: !screen.controller.running
                }
                FilesPanel {
                    Layout.fillWidth: true
                    controller: screen.controller
                    enabled: !screen.controller.running
                }
            }
        }
        Label {
            Layout.fillWidth: true
            text: screen.controller.includeSubdirectories
                ? qsTr("Includes subdirectories. File rules organize files under the input folder; folder rules also process nested folders.")
                : qsTr("File rules process files directly in this folder. Folder rules rename or move its immediate subfolders.")
            wrapMode: Text.WordWrap
        }
        Button {
            text: qsTr("Start moving files")
            enabled: !screen.controller.running && screen.controller.folder.length > 0
                && (!screen.controller.rules.some(rule => rule.id === "landscape" && rule.enabled)
                    || screen.controller.landscapeFolder.length > 0)
            onClicked: {
                log.clear()
                screen.completionSummary = ""
                screen.processed = 0
                screen.total = 0
                screen.status = qsTr("Processing…")
                screen.controller.start()
            }
        }
        ProgressBar {
            Layout.fillWidth: true
            indeterminate: screen.controller.running && screen.total === 0
            from: 0
            to: screen.total
            value: screen.processed
            visible: screen.controller.running
        }
        Label { text: screen.status }
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: 120
            Layout.minimumHeight: 80
            TextArea {
                id: log
                readOnly: true
                wrapMode: TextEdit.Wrap
                Accessible.name: qsTr("Processing log")
            }
        }
    }
    Connections {
        target: screen.controller
        function onOutput(text) { log.insert(log.length, text) }
        function onCompletionSummary(text) { screen.completionSummary = text }
        function onCompleted(code) {
            screen.status = code === 0 ? qsTr("Complete: %1").arg(screen.completionSummary) : qsTr("Process exited with code %1. See log.").arg(code)
        }
        function onProgress(current, total, seconds) {
            screen.processed = current
            screen.total = total
            screen.status = qsTr("%1 of %2 items · About %3 s remaining").arg(current).arg(total).arg(seconds)
        }
    }
}
