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
        if (close.accepted && updateLoader.status === Loader.Ready)
            updateLoader.item.close()
        if (close.accepted && extrasLoader.status === Loader.Ready)
            extrasLoader.item.close()
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
                objectName: "extrasMenu"
                text: qsTr("Extras")
                enabled: !window.controller.running && !window.controller.updates.busy
                onTriggered: {
                    extrasLoader.active = true
                    if (extrasLoader.status === Loader.Ready) {
                        extrasLoader.item.show()
                        extrasLoader.item.requestActivate()
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
        id: extrasLoader
        active: false
        sourceComponent: Component {
            Extras {
                controller: window.controller
                transientParent: window
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
