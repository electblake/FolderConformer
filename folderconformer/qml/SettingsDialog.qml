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
    width: 960
    minimumWidth: 840
    height: 460
    minimumHeight: 380
    property string selectedGroup: "general"
    readonly property string searchText: settingsSearch.text.trim().toLowerCase()
    readonly property string configTitle: qsTr("User configuration folder")
    readonly property string themeTitle: qsTr("Theme")
    readonly property string themeTooltip: qsTr("Theme changes apply after restarting the app.")
    readonly property bool configMatches: matches(configTitle, "")
    readonly property bool themeMatches: matches(themeTitle, themeTooltip)
    readonly property bool generalMatches: configMatches || themeMatches
    readonly property string emptyFileTitle: qsTr("E1 — Create empty file")
    readonly property string emptyFileTooltip: qsTr("Filename in project root")
    readonly property bool rulesMatches: matches(emptyFileTitle, emptyFileTooltip)
    readonly property string extensionsTooltip: qsTr("Separate extensions with semicolons.")
    readonly property string conflictsTitle: qsTr("Resolve name conflicts")
    readonly property string conflictsTooltip: qsTr("Number conflicting names with _1, _2, \u2026 When unchecked, skip files whose destination name already exists.")
    readonly property var fileSettings: [
        {key: "videoExtensions", title: qsTr("Video file extensions"), tooltip: extensionsTooltip},
        {key: "imageExtensions", title: qsTr("Image file extensions"), tooltip: extensionsTooltip},
        {key: "dataExtensions", title: qsTr("Data file extensions"), tooltip: extensionsTooltip}
    ]
    readonly property var folderSettings: [
        {key: "landscapeFolder", title: qsTr("Landscape folder name"), tooltip: ""},
        {key: "musicVideoFolder", title: qsTr("Music Video folder"), tooltip: ""},
        {key: "videoFolder", title: qsTr("Video folder"), tooltip: ""},
        {key: "imageFolder", title: qsTr("Image folder"), tooltip: ""},
        {key: "dataFolder", title: qsTr("Data"), tooltip: ""}
    ]
    readonly property bool conflictsMatch: matches(conflictsTitle, conflictsTooltip)
    readonly property bool filesMatch: fileSettings.some(setting => matches(setting.title, setting.tooltip)) || conflictsMatch
    readonly property bool foldersMatch: folderSettings.some(setting => matches(setting.title, setting.tooltip))
    readonly property bool fileSettingsMatch: filesMatch || foldersMatch
    readonly property var matchingGroups: [
        {key: "general", title: qsTr("General"), matches: generalMatches},
        {key: "rules", title: qsTr("Rules"), matches: rulesMatches},
        {key: "files", title: qsTr("File Settings"), matches: fileSettingsMatch}
    ].filter(group => group.matches)
    readonly property string activeGroup: matchingGroups.some(group => group.key === selectedGroup)
        ? selectedGroup : (matchingGroups.length > 0 ? matchingGroups[0].key : "")

    component SettingTextRow: ColumnLayout {
        required property var modelData
        Layout.fillWidth: true
        visible: dialog.matches(modelData.title, modelData.tooltip)
        Label { text: parent.modelData.title }
        TextField {
            id: settingField
            objectName: parent.modelData.key
            Layout.fillWidth: true
            text: dialog.controller[parent.modelData.key]
            Accessible.name: parent.modelData.title
            selectByMouse: true
            ToolTip.visible: (hovered || activeFocus) && parent.modelData.tooltip.length > 0
            ToolTip.text: parent.modelData.tooltip
            validator: parent.modelData.key === "landscapeFolder" ? landscapeValidator : null
            onTextEdited: dialog.controller[parent.modelData.key] = text
            RegularExpressionValidator {
                id: landscapeValidator
                regularExpression: /[^<>:"/\\|?*.][^<>:"/\\|?*]*/
            }
        }
    }

    function matches(title: string, tooltip: string): bool {
        return searchText.length === 0
            || title.toLowerCase().includes(searchText)
            || tooltip.toLowerCase().includes(searchText)
    }

    Shortcut {
        sequence: "Escape"
        onActivated: dialog.close()
    }

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Item {
            id: settingsLayout
            Layout.fillWidth: true
            Layout.fillHeight: true

            ColumnLayout {
                id: sidebar
                objectName: "settingsSidebar"
                width: (settingsLayout.width - 16) / 3
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                spacing: 8

                TextField {
                    id: settingsSearch
                    objectName: "settingsSearch"
                    Layout.fillWidth: true
                    placeholderText: qsTr("Search settings…")
                    Accessible.name: qsTr("Search settings")
                    selectByMouse: true
                }
                Frame {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    padding: 0
                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 0
                        ItemDelegate {
                            objectName: "generalSettingsGroup"
                            Layout.fillWidth: true
                            text: qsTr("General")
                            visible: dialog.generalMatches
                            highlighted: dialog.activeGroup === "general"
                            onClicked: dialog.selectedGroup = "general"
                        }
                        ItemDelegate {
                            objectName: "rulesSettingsGroup"
                            Layout.fillWidth: true
                            text: qsTr("Rules")
                            visible: dialog.rulesMatches
                            highlighted: dialog.activeGroup === "rules"
                            onClicked: dialog.selectedGroup = "rules"
                        }
                        ItemDelegate {
                            objectName: "fileSettingsGroup"
                            Layout.fillWidth: true
                            text: qsTr("File Settings")
                            visible: dialog.fileSettingsMatch
                            highlighted: dialog.activeGroup === "files"
                            onClicked: dialog.selectedGroup = "files"
                        }
                        Item { Layout.fillHeight: true }
                    }
                }
            }
            ScrollView {
                id: settingsScroll
                anchors.left: sidebar.right
                anchors.leftMargin: 16
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                contentWidth: availableWidth
                clip: true
                ColumnLayout {
                    width: settingsScroll.availableWidth
                    spacing: 12
                    Label {
                        Layout.fillWidth: true
                        text: ({general: qsTr("General"), rules: qsTr("Rules"), files: qsTr("File Settings"), "": ""})[dialog.activeGroup]
                        font.bold: true
                        font.pixelSize: 20
                        visible: dialog.matchingGroups.length > 0
                    }
                    ColumnLayout {
                        objectName: "generalSettingsPage"
                        Layout.fillWidth: true
                        visible: dialog.activeGroup === "general" && dialog.generalMatches
                        spacing: 12
                        GroupBox {
                            title: qsTr("Data")
                            visible: dialog.configMatches
                            Layout.fillWidth: true
                            ColumnLayout {
                                anchors.fill: parent
                                Label { text: dialog.configTitle }
                                RowLayout {
                                    Layout.fillWidth: true
                                    TextField {
                                        objectName: "configFolder"
                                        Layout.fillWidth: true
                                        text: dialog.controller.configFolder
                                        Accessible.name: dialog.configTitle
                                        onEditingFinished: dialog.controller.configFolder = text
                                    }
                                    Button {
                                        objectName: "browseConfigFolder"
                                        text: qsTr("Browse\u2026")
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
                            visible: dialog.themeMatches
                            Layout.fillWidth: true
                            ColumnLayout {
                                anchors.fill: parent
                                Label { text: dialog.themeTitle }
                                RowLayout {
                                    Layout.fillWidth: true
                                    ComboBox {
                                        objectName: "themeSelector"
                                        Layout.fillWidth: true
                                        model: dialog.controller.themes.map(name => name === "" ? qsTr("System default") : name)
                                        currentIndex: dialog.controller.themes.indexOf(dialog.controller.theme)
                                        Accessible.name: dialog.themeTitle
                                        ToolTip.visible: hovered || activeFocus
                                        ToolTip.text: dialog.themeTooltip
                                        onActivated: dialog.controller.theme = dialog.controller.themes[currentIndex]
                                    }
                                    Button {
                                        objectName: "restartAndApply"
                                        text: qsTr("Restart && Apply")
                                        enabled: !dialog.controller.running && !dialog.controller.updates.busy
                                        onClicked: dialog.controller.restart()
                                    }
                                }
                            }
                        }
                    }
                    ColumnLayout {
                        objectName: "rulesSettingsPage"
                        Layout.fillWidth: true
                        visible: dialog.activeGroup === "rules" && dialog.rulesMatches
                        spacing: 12
                        GroupBox {
                            objectName: "fileRulesSettings"
                            title: qsTr("File Rules")
                            Layout.fillWidth: true
                            ColumnLayout {
                                anchors.fill: parent
                                Label { text: dialog.emptyFileTitle }
                                TextField {
                                    objectName: "create_empty_fileFileName"
                                    Layout.fillWidth: true
                                    text: dialog.controller.emptyFileName
                                    placeholderText: ".forceGallery"
                                    Accessible.name: dialog.emptyFileTooltip
                                    ToolTip.visible: hovered || activeFocus
                                    ToolTip.text: dialog.emptyFileTooltip
                                    enabled: !dialog.controller.running
                                    selectByMouse: true
                                    onEditingFinished: dialog.controller.emptyFileName = text
                                }
                            }
                        }
                        GroupBox {
                            objectName: "folderRulesSettings"
                            title: qsTr("Folder Rules")
                            Layout.fillWidth: true
                            visible: dialog.searchText.length === 0
                            Label { text: qsTr("No settings in this group yet.") }
                        }
                    }
                    ColumnLayout {
                        objectName: "fileSettingsPage"
                        Layout.fillWidth: true
                        visible: dialog.activeGroup === "files" && dialog.fileSettingsMatch
                        enabled: !dialog.controller.running && !dialog.controller.updates.busy
                        spacing: 12
                        GroupBox {
                            objectName: "filesSettingsFields"
                            title: qsTr("Files")
                            Layout.fillWidth: true
                            visible: dialog.filesMatch
                            ColumnLayout {
                                anchors.fill: parent
                                Repeater {
                                    model: dialog.fileSettings
                                    delegate: SettingTextRow {}
                                }
                                CheckBox {
                                    objectName: "enumerateConflicts"
                                    Layout.fillWidth: true
                                    visible: dialog.conflictsMatch
                                    text: dialog.conflictsTitle
                                    checked: dialog.controller.enumerateConflicts
                                    ToolTip.visible: hovered || activeFocus
                                    ToolTip.text: dialog.conflictsTooltip
                                    onToggled: dialog.controller.enumerateConflicts = checked
                                }
                            }
                        }
                        GroupBox {
                            objectName: "foldersSettingsFields"
                            title: qsTr("Folders")
                            Layout.fillWidth: true
                            visible: dialog.foldersMatch
                            ColumnLayout {
                                anchors.fill: parent
                                Repeater {
                                    model: dialog.folderSettings
                                    delegate: SettingTextRow {}
                                }
                            }
                        }
                    }
                    Label {
                        objectName: "noMatchingSettings"
                        Layout.fillWidth: true
                        visible: dialog.matchingGroups.length === 0
                        text: qsTr("No settings match your search.")
                        wrapMode: Text.WordWrap
                    }
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
