import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Pane {
    id: screen
    objectName: "conformerScreen"
    required property QtObject controller
    property string status: qsTr("Ready")
    property string statusDetails: ""
    property string completionSummary: ""
    property int processed: 0
    property int total: 0
    property int remainingSeconds: 0
    function scrollOutputToBottom() {
        outputScroll.contentItem.contentY = Math.max(0, outputScroll.contentItem.contentHeight - outputScroll.contentItem.height)
    }
    implicitHeight: contentLayout.Layout.minimumHeight + topPadding + bottomPadding

    ColumnLayout {
        id: contentLayout
        anchors.fill: parent
        spacing: 12

        ScrollView {
            id: settingsScroll
            objectName: "settingsScroll"
            implicitWidth: 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: 800
            Layout.minimumHeight: rulesPanel.topPadding + rulesPanel.bottomPadding + rulesPanel.font.pixelSize * 3
            contentWidth: Math.max(availableWidth, rulesPanel.implicitWidth)
            clip: true
            RulesPanel {
                id: rulesPanel
                width: settingsScroll.contentWidth
                controller: screen.controller
                enabled: !screen.controller.running
                onRunOnceRequested: function(index) {
                    screen.completionSummary = ""
                    screen.processed = 0
                    screen.total = 0
                    screen.remainingSeconds = 0
                    screen.status = qsTr("Processing…")
                    screen.statusDetails = ""
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
                        screen.completionSummary = ""
                        screen.processed = 0
                        screen.total = 0
                        screen.remainingSeconds = 0
                        screen.status = qsTr("Processing…")
                        screen.statusDetails = ""
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
        RowLayout {
            Layout.fillWidth: true
            Label {
                objectName: "processingStatus"
                HoverHandler { id: statusHover }
                ToolTip.visible: statusHover.hovered
                ToolTip.text: screen.controller.runState === "pausing" ? qsTr("Pausing after current rules…")
                    : screen.controller.runState === "stopping" ? qsTr("Stopping after current rules…")
                    : screen.statusDetails
                text: screen.controller.runState === "pausing" ? qsTr("Pausing…")
                    : screen.controller.runState === "paused" ? qsTr("Paused")
                    : screen.controller.runState === "stopping" ? qsTr("Stopping…")
                    : screen.controller.runState === "cancelling" ? qsTr("Cancelling…")
                    : screen.status
            }
            Item { Layout.fillWidth: true }
            Label {
                objectName: "processingEta"
                text: qsTr("ETA %1:%2:%3")
                    .arg(String(Math.floor(screen.remainingSeconds / 3600)).padStart(2, "0"))
                    .arg(String(Math.floor(screen.remainingSeconds / 60) % 60).padStart(2, "0"))
                    .arg(String(screen.remainingSeconds % 60).padStart(2, "0"))
            }
        }
        ScrollView {
            id: outputScroll
            objectName: "outputScroll"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: 120
            Layout.minimumHeight: 80
            TextArea {
                id: log
                objectName: "applicationLog"
                textFormat: TextEdit.PlainText
                readOnly: true
                wrapMode: TextEdit.Wrap
                Accessible.name: qsTr("Application log")
            }
        }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            Button {
                objectName: "clearOutput"
                text: qsTr("Clear Output")
                onClicked: screen.controller.clearOutput()
            }
            Button {
                objectName: "copyOutput"
                text: qsTr("Copy Output")
                onClicked: {
                    log.selectAll()
                    log.copy()
                }
            }
            Button {
                objectName: "goToBottom"
                text: qsTr("Go to Bottom")
                onClicked: screen.scrollOutputToBottom()
            }
        }
    }
    Connections {
        target: screen.controller
        function onOutput(text) {
            const previousY = outputScroll.contentItem.contentY
            const atBottom = previousY + outputScroll.contentItem.height >= outputScroll.contentItem.contentHeight - 1
            let retained = log.text + text
            if (retained.length > 100000) {
                const cut = retained.indexOf("\n", retained.length - 100001)
                retained = cut >= 0 ? retained.slice(cut + 1) : retained.slice(0, 100000)
            }
            log.text = retained.split("\n").slice(-1001).join("\n")
            Qt.callLater(function() {
                if (atBottom)
                    screen.scrollOutputToBottom()
                else
                    outputScroll.contentItem.contentY = Math.min(previousY, Math.max(0, outputScroll.contentItem.contentHeight - outputScroll.contentItem.height))
            })
        }
        function onOutputCleared() { log.clear() }
        function onCompletionSummary(text) { screen.completionSummary = text }
        function onCompleted(code) {
            screen.remainingSeconds = 0
            screen.status = screen.controller.runState === "cancelled" ? qsTr("Cancelled")
                : screen.controller.runState === "stopped" ? qsTr("Stopped")
                : code === 0 ? qsTr("Complete") : qsTr("Failed")
            screen.statusDetails = screen.controller.runState === "cancelled" ? ""
                : screen.controller.runState === "stopped" || code === 0 ? screen.completionSummary
                : qsTr("Process exited with code %1. See log.").arg(code)
        }
        function onProgress(current, total, seconds) {
            screen.processed = current
            screen.total = total
            screen.status = qsTr("%1 / %2").arg(current).arg(total)
            screen.remainingSeconds = seconds
            screen.statusDetails = ""
        }
    }
}
