pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs

ApplicationWindow {
    id: window
    required property QtObject controller
    property bool nativeMenus: false
    property var pending_installer: null
    signal quitRequested()
    property bool inputVisible: true
    signal inputToggled(bool visible)
    property bool previewVisible: true
    signal previewToggled(bool visible)
    property bool performanceVisible: true
    signal performanceToggled(bool visible)
    property bool choosingFolder: false
    property bool foldersVisible: true
    signal foldersToggled(bool visible)
    property bool filesVisible: true
    signal filesToggled(bool visible)
    property bool audioVisible: true
    signal audioToggled(bool visible)
    signal resetLayoutRequested()
    width: 820
    height: 720
    minimumWidth: 640
    minimumHeight: Math.max(560, conformerScreen.implicitHeight + menuBar.height)
    visible: true
    title: qsTr("FolderConformer %1").arg(Qt.application.version)
    onClosing: function(close) {
        close.accepted = !window.controller.running && !window.controller.updates.busy
        if (close.accepted)
            closeDialogs()
    }
    function closeDialogs() {
        window.choosingFolder = false
        if (settingsLoader.status === Loader.Ready)
            settingsLoader.item.close()
        if (updateLoader.status === Loader.Ready)
            updateLoader.item.close()
        if (installExplorerLoader.status === Loader.Ready)
            installExplorerLoader.item.close()
        if (completionLoader.status === Loader.Ready)
            completionLoader.item.close()
    }

    menuBar: MenuBar {
        visible: !window.nativeMenus
        height: visible ? implicitHeight : 0
        Menu {
            title: qsTr("&File")
            MenuItem {
                objectName: "selectFolderMenu"
                text: qsTr("Select Folder..")
                enabled: !window.controller.running && !window.controller.updates.busy
                onTriggered: window.choosingFolder = true
            }
            MenuItem {
                objectName: "settingsMenu"
                text: qsTr("&Settings…")
                enabled: !window.controller.running && !window.controller.updates.busy
                onTriggered: {
                    settingsLoader.active = true
                    settingsLoader.item.show()
                    settingsLoader.item.requestActivate()
                }
            }
            MenuSeparator {}
            MenuItem {
                objectName: "quitMenu"
                text: qsTr("&Quit")
                enabled: !window.controller.running && !window.controller.updates.busy
                onTriggered: window.quitRequested()
            }
        }
        Menu {
            title: qsTr("&View")
            MenuItem {
                objectName: "inputFolderMenu"
                text: qsTr("I&nput folder")
                checkable: true
                checked: window.inputVisible
                onTriggered: window.inputToggled(!window.inputVisible)
            }
            MenuItem {
                objectName: "previewMenu"
                text: qsTr("&Conformant Folder")
                checkable: true
                checked: window.previewVisible
                onTriggered: window.previewToggled(!window.previewVisible)
            }
            MenuItem {
                objectName: "performanceMenu"
                text: qsTr("&Performance")
                checkable: true
                checked: window.performanceVisible
                onTriggered: window.performanceToggled(!window.performanceVisible)
            }
            MenuItem {
                objectName: "foldersMenu"
                text: qsTr("&Folders")
                checkable: true
                checked: window.foldersVisible
                onTriggered: window.foldersToggled(!window.foldersVisible)
            }
            MenuItem {
                objectName: "filesMenu"
                text: qsTr("F&iles")
                checkable: true
                checked: window.filesVisible
                onTriggered: window.filesToggled(!window.filesVisible)
            }
            MenuItem {
                objectName: "audioMenu"
                text: qsTr("&Audio")
                checkable: true
                checked: window.audioVisible
                onTriggered: window.audioToggled(!window.audioVisible)
            }
            MenuSeparator {}
            MenuItem {
                objectName: "resetLayoutMenu"
                text: qsTr("&Reset Layout")
                onTriggered: window.resetLayoutRequested()
            }
        }
        Menu {
            title: qsTr("Help")
            MenuItem {
                objectName: "installExplorerMenu"
                text: qsTr("Install for File Explorer")
                enabled: !window.controller.running && !window.controller.updates.busy
                onTriggered: {
                    installExplorerLoader.active = true
                    if (installExplorerLoader.status === Loader.Ready) {
                        installExplorerLoader.item.show()
                        installExplorerLoader.item.requestActivate()
                    }
                }
            }
            MenuItem {
                objectName: "checkForUpdatesMenu"
                text: qsTr("Check for updates..")
                enabled: !window.controller.running && !window.controller.updates.busy
                onTriggered: {
                    updateLoader.active = true
                    if (updateLoader.status === Loader.Ready) {
                        updateLoader.item.show()
                        updateLoader.item.requestActivate()
                        window.controller.updates.check()
                    }
                }
            }
        }
    }

    Loader {
        active: window.choosingFolder
        sourceComponent: Component {
            FolderDialog {
                title: qsTr("Select input folder")
                Component.onCompleted: open()
                onAccepted: {
                    window.controller.selectFolder(selectedFolder)
                    window.choosingFolder = false
                }
                onRejected: window.choosingFolder = false
            }
        }
    }

    Loader {
        id: settingsLoader
        active: false
        sourceComponent: Component {
            SettingsDialog {
                controller: window.controller
                transientParent: window
                palette: window.palette
            }
        }
    }

    Loader {
        id: installExplorerLoader
        active: false
        sourceComponent: Component {
            InstallExplorer {
                controller: window.controller
                transientParent: window
                palette: window.palette
            }
        }
    }

    Loader {
        id: updateLoader
        active: false
        sourceComponent: Component {
            SoftwareUpdate {
                updater: window.controller.updates
                transientParent: window
                palette: window.palette
                onInstallRequested: {
                    window.pending_installer = window.controller.updates.installerPath
                    window.quitRequested()
                }
            }
        }
    }

    Loader {
        id: completionLoader
        active: false
        sourceComponent: Component {
            ConformingComplete {
                controller: window.controller
                transientParent: window
                palette: window.palette
                onQuitRequested: window.quitRequested()
            }
        }
    }

    Connections {
        target: window.controller
        function onCompleted(code) {
            if (code === 0 && window.controller.runState === "") {
                completionLoader.active = true
                if (completionLoader.status === Loader.Ready) {
                    completionLoader.item.show()
                    completionLoader.item.requestActivate()
                }
            }
        }
    }

    ConformerScreen {
        id: conformerScreen
        anchors.fill: parent
        controller: window.controller
        enabled: !window.controller.updates.busy
    }
}
