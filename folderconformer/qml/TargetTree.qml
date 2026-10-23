pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

GroupBox {
    id: panel
    objectName: "targetTreePanel"
    required property QtObject controller
    title: qsTr("Target folder preview")
    contentHeight: tree.implicitHeight

    FontMetrics { id: metrics }

    TreeView {
        id: tree
        objectName: "targetTree"
        anchors.fill: parent
        implicitHeight: rows * (metrics.height + 12)
        model: panel.controller.targetTree
        clip: true
        interactive: false
        activeFocusOnTab: true
        editTriggers: TableView.NoEditTriggers
        Accessible.name: qsTr("Target folder preview")
        delegate: TreeViewDelegate {
            implicitWidth: tree.width
            implicitHeight: metrics.height + 12
        }
        Component.onCompleted: expandRecursively()
    }
    Connections {
        target: panel.controller
        function onTargetTreeRulesChanged() { tree.expandRecursively() }
    }
}
