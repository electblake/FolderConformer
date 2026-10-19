import QtQuick
import QtQuick.Controls

ApplicationWindow {
    id: window
    required property QtObject controller
    width: 820
    height: 720
    minimumWidth: 640
    minimumHeight: 560
    visible: true
    title: qsTr("FolderConformer %1").arg(Qt.application.version)
    onClosing: function(close) { close.accepted = !window.controller.running }

    ConformerScreen {
        anchors.fill: parent
        controller: window.controller
    }
}
