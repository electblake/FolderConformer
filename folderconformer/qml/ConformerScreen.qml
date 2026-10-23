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

        FolderPanel {
            id: folderPanel
            Layout.fillWidth: true
            controller: screen.controller
            enabled: !screen.controller.running
        }
        ScrollView {
            id: settingsScroll
            objectName: "settingsScroll"
            implicitWidth: 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: 800
            contentWidth: Math.max(availableWidth, rulesPanel.implicitWidth)
            clip: true
            RulesPanel {
                id: rulesPanel
                width: settingsScroll.contentWidth
                controller: screen.controller
                enabled: !screen.controller.running
                onRunOnceRequested: function(index) {
                    log.clear()
                    screen.completionSummary = ""
                    screen.processed = 0
                    screen.total = 0
                    screen.status = qsTr("Processing…")
                    screen.controller.start(index)
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: screen.availableWidth >= processingActions.implicitWidth + outputActions.implicitWidth + columnSpacing ? 2 : 1
            RowLayout {
                id: processingActions
                Layout.fillWidth: true
                Button {
                    objectName: "executeRules"
                    text: qsTr("Execute rules")
                    enabled: !screen.controller.running && screen.controller.folder.length > 0
                        && (!screen.controller.rules.some(rule => (rule.id === "landscape" || rule.id === "landscape_images") && rule.enabled)
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
                Button {
                    objectName: "checkAll"
                    text: qsTr("Check all")
                    enabled: !screen.controller.running && screen.controller.folder.length > 0
                        && screen.controller.rules.some(rule => rule.enabled)
                    onClicked: screen.controller.checkAll()
                }
                Button {
                    objectName: "pauseProcessing"
                    text: screen.controller.runState === "paused" || screen.controller.runState === "pausing"
                        ? qsTr("Resume") : qsTr("Pause")
                    enabled: screen.controller.running && !screen.controller.checking && screen.controller.runState !== "stopping"
                        && screen.controller.runState !== "cancelling"
                    onClicked: screen.controller.pause()
                }
                Button {
                    objectName: "stopProcessing"
                    text: qsTr("Stop")
                    enabled: screen.controller.running && !screen.controller.checking && screen.controller.runState !== "stopping"
                        && screen.controller.runState !== "cancelling"
                    onClicked: screen.controller.stop()
                }
                Button {
                    objectName: "cancelProcessing"
                    text: qsTr("Cancel")
                    enabled: screen.controller.running && screen.controller.runState !== "cancelling"
                    onClicked: screen.controller.cancel()
                }
                Item { Layout.fillWidth: true }
            }
            RowLayout {
                id: outputActions
                Layout.alignment: Qt.AlignRight
                Button {
                    objectName: "openOutputFolder"
                    text: qsTr("Open Output Folder")
                    enabled: screen.controller.folder.length > 0
                    onClicked: screen.controller.openOutputFolder()
                }
            }
        }
        ProgressBar {
            Layout.fillWidth: true
            indeterminate: screen.controller.running && screen.total === 0
            from: 0
            to: screen.total
            value: screen.processed
            visible: screen.controller.running && !screen.controller.checking
        }
        Label {
            text: screen.controller.runState === "pausing" ? qsTr("Pausing after current rules…")
                : screen.controller.runState === "paused" ? qsTr("Paused")
                : screen.controller.runState === "stopping" ? qsTr("Stopping after current rules…")
                : screen.controller.runState === "cancelling" ? qsTr("Cancelling…")
                : screen.status
        }
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
        Button {
            objectName: "copyOutput"
            Layout.alignment: Qt.AlignRight
            text: qsTr("Copy Output")
            onClicked: {
                log.selectAll()
                log.copy()
            }
        }
    }
    Connections {
        target: screen.controller
        function onOutput(text) { log.insert(log.length, text) }
        function onCompletionSummary(text) { screen.completionSummary = text }
        function onCompleted(code) {
            screen.status = screen.controller.runState === "cancelled" ? qsTr("Cancelled")
                : screen.controller.runState === "stopped" ? qsTr("Stopped: %1").arg(screen.completionSummary)
                : code === 0 ? qsTr("Complete: %1").arg(screen.completionSummary) : qsTr("Process exited with code %1. See log.").arg(code)
        }
        function onProgress(current, total, seconds) {
            screen.processed = current
            screen.total = total
            screen.status = qsTr("%1 of %2 items · About %3 s remaining").arg(current).arg(total).arg(seconds)
        }
    }
}
