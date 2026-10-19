import QtQuick
import QtQuick.Controls

ApplicationWindow {
    id: window
    required property QtObject controller
    property var pending_installer: null
    width: 820
    height: 720
    minimumWidth: 640
    minimumHeight: 560
    visible: true
    title: qsTr("FolderConformer %1").arg(Qt.application.version)
    onClosing: function(close) {
        close.accepted = !window.controller.running && !window.controller.updates.busy
        if (close.accepted && settingsLoader.status === Loader.Ready)
            settingsLoader.item.close()
        if (close.accepted && updateLoader.status === Loader.Ready)
            updateLoader.item.close()
        if (close.accepted && installExplorerLoader.status === Loader.Ready)
            installExplorerLoader.item.close()
    }

    menuBar: MenuBar {
        Menu {
            title: qsTr("&File")
            MenuItem {
                objectName: "selectFolderMenu"
                text: qsTr("Select Folder..")
                enabled: !window.controller.running && !window.controller.updates.busy
                onTriggered: conformerScreen.choosingFolder = true
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
                onTriggered: window.close()
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
                    window.close()
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
