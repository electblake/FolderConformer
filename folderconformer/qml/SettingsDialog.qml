pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

ApplicationWindow {
    id: dialog
    objectName: "settingsDialog"
    required property QtObject controller
    property bool choosing: false
    title: qsTr("Settings")
    flags: Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
    modality: Qt.WindowModal
    width: 720
    minimumWidth: 640
    height: content.implicitHeight + 32
    minimumHeight: content.implicitHeight + 32

    Shortcut {
        sequence: "Escape"
        onActivated: dialog.close()
    }

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        GroupBox {
            title: qsTr("Data")
            Layout.fillWidth: true
            GridLayout {
                anchors.fill: parent
                columns: 2
                Label { text: qsTr("User configuration folder") }
                RowLayout {
                    Layout.fillWidth: true
                    TextField {
                        objectName: "configFolder"
                        Layout.fillWidth: true
                        text: dialog.controller.configFolder
                        Accessible.name: qsTr("User configuration folder")
                        onEditingFinished: dialog.controller.configFolder = text
                    }
                    Button {
                        objectName: "browseConfigFolder"
                        text: qsTr("Browse…")
                        onClicked: dialog.choosing = true
                    }
                    Button {
                        objectName: "openConfigFolder"
                        text: qsTr("Open")
                        onClicked: dialog.controller.openConfigFolder()
                    }
                }
            }
        }
        GroupBox {
            title: qsTr("Appearance")
            Layout.fillWidth: true
            GridLayout {
                anchors.fill: parent
                columns: 2
                Label { text: qsTr("Theme") }
                RowLayout {
                    Layout.fillWidth: true
                    ComboBox {
                        objectName: "themeSelector"
                        Layout.fillWidth: true
                        model: dialog.controller.themes.map(name => name === "" ? qsTr("System default") : name)
                        currentIndex: dialog.controller.themes.indexOf(dialog.controller.theme)
                        Accessible.name: qsTr("Theme")
                        onActivated: dialog.controller.theme = dialog.controller.themes[currentIndex]
                    }
                    Button {
                        objectName: "restartAndApply"
                        text: qsTr("Restart && Apply")
                        enabled: !dialog.controller.running && !dialog.controller.updates.busy
                        onClicked: dialog.controller.restart()
                    }
                }
                Label {
                    Layout.columnSpan: 2
                    text: qsTr("Theme changes apply after restarting the app.")
                }
            }
        }
        Button {
            objectName: "closeSettings"
            Layout.alignment: Qt.AlignRight
            text: qsTr("Close")
            onClicked: dialog.close()
        }
    }
    Loader {
        active: dialog.choosing
        sourceComponent: Component {
            FolderDialog {
                title: qsTr("Select user configuration folder")
                Component.onCompleted: open()
                onAccepted: {
                    dialog.controller.selectConfigFolder(selectedFolder)
                    dialog.choosing = false
                }
                onRejected: dialog.choosing = false
            }
        }
    }
}
