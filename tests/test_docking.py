import tempfile
import unittest
from pathlib import Path
from unittest.mock import PropertyMock, patch

from PySide6.QtCore import QEvent, QMetaObject, QObject, Qt, QUrl
from PySide6.QtGui import QKeyEvent, QValidator
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDockWidget, QLineEdit

from folderconformer.app import Controller, MainWindow


APP = QApplication.instance() or QApplication([])


class DockingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.enterContext(patch("folderconformer.app.user_config_path", return_value=Path(temporary.name)))
        self.controller = Controller()
        self.engine = QQmlApplicationEngine()
        self.messages = []
        self.engine.warnings.connect(lambda warnings: self.messages.extend(warning.toString() for warning in warnings))
        self.engine.setInitialProperties({"controller": self.controller, "visible": False})
        self.engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
        self.quick = self.engine.rootObjects()[0]
        self.host = MainWindow(self.controller, self.quick)
        self.host.show()
        QTest.qWait(100)

    def tearDown(self):
        self.controller.updates._busy = False
        self.controller.updates.changed.emit()
        self.host.close()
        self.host.deleteLater()
        APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.engine.deleteLater()
        APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertEqual(self.messages, [])

    def test_native_dock_moves_floats_closes_and_reopens(self):
        dock = self.host.folders_dock
        self.assertIsInstance(dock, QDockWidget)
        self.assertEqual(self.host.dockWidgetArea(dock), Qt.DockWidgetArea.RightDockWidgetArea)
        self.assertEqual(len(dock.findChildren(QLineEdit)), 3)
        self.assertIsNone(self.quick.findChild(QObject, "ruleFoldersPanel"))
        dock.setFloating(True)
        QTest.qWait(30)
        self.assertTrue(dock.isFloating())
        dock.setFloating(False)
        self.host.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self.assertEqual(self.host.dockWidgetArea(dock), Qt.DockWidgetArea.LeftDockWidgetArea)
        dock.close()
        self.assertFalse(self.quick.property("foldersVisible"))
        menu = self.quick.findChild(QObject, "foldersMenu")
        QMetaObject.invokeMethod(menu, "triggered")
        APP.processEvents()
        self.assertTrue(dock.isVisible())
        self.assertTrue(menu.property("checked"))
        QMetaObject.invokeMethod(menu, "triggered")
        self.assertFalse(dock.isVisible())
        QMetaObject.invokeMethod(menu, "triggered")
        self.assertTrue(dock.isVisible())

    def test_folder_edits_persist_update_rules_and_keep_keyboard_order(self):
        values = {"landscapeFolder": "Wide media é", "videoFolder": "Clips/", "imageFolder": "Pictures/"}
        fields = list(self.host.folder_fields.values())
        self.host.activateWindow()
        for name, value in values.items():
            field = self.host.folder_fields[name]
            field.setFocus()
            QTest.keyClick(field, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            APP.sendEvent(field, QKeyEvent(QEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, value))
            self.assertEqual(getattr(self.controller, name), value)
            self.assertEqual(getattr(Controller(), name), value)
        fields[0].setFocus()
        QTest.keyClick(fields[0], Qt.Key.Key_Tab)
        self.assertTrue(fields[1].hasFocus())
        QTest.keyClick(fields[1], Qt.Key.Key_Tab)
        self.assertTrue(fields[2].hasFocus())
        self.controller.videoFolder = "Updated/"
        self.assertEqual(fields[1].text(), "Updated/")
        self.assertEqual(fields[0].validator().validate("bad/name", 0)[0], QValidator.State.Invalid)

    def test_busy_locks_and_close_apply_to_native_host(self):
        self.controller.updates._busy = True
        self.controller.updates.changed.emit()
        self.assertTrue(all(not field.isEnabled() for field in self.host.folder_fields.values()))
        self.assertFalse(self.host.close())
        self.assertTrue(self.host.isVisible())
        self.controller.updates._busy = False
        self.controller.updates.changed.emit()
        self.assertTrue(all(field.isEnabled() for field in self.host.folder_fields.values()))
        with patch.object(Controller, "running", new_callable=PropertyMock, return_value=True):
            self.controller.runningChanged.emit()
            self.assertFalse(self.host.close())
            self.assertTrue(all(not field.isEnabled() for field in self.host.folder_fields.values()))
        self.controller.runningChanged.emit()
        QMetaObject.invokeMethod(self.quick.findChild(QObject, "settingsMenu"), "triggered")
        APP.processEvents()
        dialog = self.quick.findChild(QObject, "settingsDialog")
        self.assertTrue(dialog.isVisible())
        self.host.folders_dock.setFloating(True)
        self.assertTrue(self.host.close())
        self.assertFalse(dialog.isVisible())
        self.assertFalse(self.host.folders_dock.isVisible())

    def test_file_quit_closes_native_host(self):
        QMetaObject.invokeMethod(self.quick.findChild(QObject, "quitMenu"), "triggered")
        APP.processEvents()
        self.assertFalse(self.host.isVisible())

    def test_install_update_closes_host_and_floating_dock(self):
        with patch.object(self.controller.updates, "check"):
            QMetaObject.invokeMethod(self.quick.findChild(QObject, "checkForUpdatesMenu"), "triggered")
        dialog = self.quick.findChild(QObject, "softwareUpdate")
        self.controller.updates._installer_path = "C:/cache/installer.exe"
        self.host.folders_dock.setFloating(True)
        QMetaObject.invokeMethod(dialog, "installRequested")
        APP.processEvents()
        self.assertFalse(self.host.isVisible())
        self.assertFalse(self.host.folders_dock.isVisible())
        self.assertEqual(self.quick.property("pending_installer"), "C:/cache/installer.exe")

    def test_large_font_and_small_window_keep_fields_accessible(self):
        font = self.host.font()
        font.setPointSize(18)
        self.host.setFont(font)
        self.host.resize(900, 600)
        APP.processEvents()
        for field in self.host.folder_fields.values():
            self.assertGreaterEqual(field.height(), field.sizeHint().height())
            self.assertGreaterEqual(field.width(), field.minimumSizeHint().width())
        scroll = self.host.folders_dock.widget()
        self.assertTrue(scroll.widgetResizable())
        self.assertGreaterEqual(self.quick.width(), 640)
