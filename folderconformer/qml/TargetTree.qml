pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Fusion
import QtQuick.Layouts

Pane {
    id: panel
    objectName: "targetTreePanel"
    required property QtObject controller
    enabled: !panel.controller.updates.busy
    contentWidth: contents.implicitWidth
    contentHeight: contents.implicitHeight

    FontMetrics {
        id: metrics
        font: panel.font
    }

    ColumnLayout {
        id: contents
        anchors.fill: parent
        spacing: 8

        RowLayout {
            Layout.alignment: Qt.AlignRight
            Button {
                objectName: "collapseTargetTree"
                text: qsTr("Collapse all")
                onClicked: tree.collapseRecursively()
            }
            Button {
                objectName: "openTargetTree"
                text: qsTr("Open all")
                onClicked: tree.expandRecursively()
            }
        }
        TreeView {
            id: tree
            objectName: "targetTree"
            Layout.fillWidth: true
            Layout.fillHeight: true
            implicitHeight: 3 * (metrics.height + 12)
            model: panel.controller.targetTree
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            activeFocusOnTab: true
            editTriggers: TableView.NoEditTriggers
            Accessible.name: qsTr("Target folder preview")
            ScrollBar.vertical: ScrollBar { objectName: "targetTreeScrollBar" }
            delegate: TreeViewDelegate {
                implicitWidth: tree.width
                implicitHeight: metrics.height + 12
            }
        }
    }
}
