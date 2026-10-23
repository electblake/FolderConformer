import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import PropertyMock, patch

from PySide6.QtCore import QEvent, QMetaObject, QObject, QPointF, Qt, QUrl
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
        self.assertEqual(len(dock.findChildren(QLineEdit)), 4)
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
        values = {"landscapeFolder": "Wide media é", "videoFolder": "Clips/", "imageFolder": "Pictures/", "dataFolder": "Records/"}
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

    def test_files_dock_starts_below_folders_and_reopens_independently(self):
        dock = self.host.files_dock
        folders = self.host.folders_dock
        self.assertIsInstance(dock, QDockWidget)
        self.assertEqual(self.host.dockWidgetArea(dock), Qt.DockWidgetArea.RightDockWidgetArea)
        self.assertGreaterEqual(dock.y(), folders.y() + folders.height())
        self.assertEqual(dock.x(), folders.x())
        self.assertEqual(len(dock.findChildren(QLineEdit)), 3)
        self.assertIsNone(self.quick.findChild(QObject, "filesPanel"))
        dock.setFloating(True)
        self.assertTrue(dock.isFloating())
        dock.close()
        self.assertFalse(self.quick.property("filesVisible"))
        self.assertTrue(folders.isVisible())
        menu = self.quick.findChild(QObject, "filesMenu")
        QMetaObject.invokeMethod(menu, "triggered")
        self.assertTrue(dock.isVisible())
        self.assertTrue(menu.property("checked"))
        dock.setFloating(False)
        self.host.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self.assertEqual(self.host.dockWidgetArea(dock), Qt.DockWidgetArea.LeftDockWidgetArea)

    def test_extension_edits_persist_and_keep_keyboard_order(self):
        self.host.activateWindow()
        fields = list(self.host.file_fields.values())
        for name, value in (("videoExtensions", "mxf;MP4"), ("imageExtensions", "gif;png"), ("dataExtensions", " .CSV;db;txt;")):
            field = self.host.file_fields[name]
            field.setFocus()
            QTest.keyClick(field, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            QTest.keyClicks(field, value)
            self.assertEqual(getattr(self.controller, name), value)
            self.assertEqual(getattr(Controller(), name), value)
        fields[0].setFocus()
        QTest.keyClick(fields[0], Qt.Key.Key_Tab)
        self.assertTrue(fields[1].hasFocus())
        self.controller.imageExtensions = "webp;jpg"
        self.assertEqual(fields[1].text(), "webp;jpg")

    def test_busy_locks_and_close_apply_to_native_host(self):
        fields = [*self.host.folder_fields.values(), *self.host.file_fields.values(), self.host.enumerate_conflicts]
        self.controller.updates._busy = True
        self.controller.updates.changed.emit()
        self.assertTrue(all(not field.isEnabled() for field in fields))
        self.assertFalse(self.host.close())
        self.assertTrue(self.host.isVisible())
        self.controller.updates._busy = False
        self.controller.updates.changed.emit()
        self.assertTrue(all(field.isEnabled() for field in fields))
        with patch.object(Controller, "running", new_callable=PropertyMock, return_value=True):
            self.controller.runningChanged.emit()
            self.assertFalse(self.host.close())
            self.assertTrue(all(not field.isEnabled() for field in fields))
        self.controller.runningChanged.emit()
        QMetaObject.invokeMethod(self.quick.findChild(QObject, "settingsMenu"), "triggered")
        APP.processEvents()
        dialog = self.quick.findChild(QObject, "settingsDialog")
        self.assertTrue(dialog.isVisible())
        self.host.folders_dock.setFloating(True)
        self.host.files_dock.setFloating(True)
        self.assertTrue(self.host.close())
        self.assertFalse(dialog.isVisible())
        self.assertFalse(self.host.folders_dock.isVisible())
        self.assertFalse(self.host.files_dock.isVisible())

    def test_reset_layout_redocks_and_reopens_both_docks(self):
        self.controller.enumerateConflicts = True
        geometry = self.host.geometry()
        self.host.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.host.folders_dock)
        self.host.files_dock.setFloating(True)
        self.host.files_dock.resize(450, 400)
        self.host.folders_dock.close()
        self.host.files_dock.close()
        menu = self.quick.findChild(QObject, "resetLayoutMenu")
        QMetaObject.invokeMethod(menu, "triggered")
        APP.processEvents()
        for dock, name in ((self.host.folders_dock, "foldersMenu"), (self.host.files_dock, "filesMenu")):
            self.assertEqual(self.host.dockWidgetArea(dock), Qt.DockWidgetArea.RightDockWidgetArea)
            self.assertFalse(dock.isFloating())
            self.assertTrue(dock.isVisible())
            self.assertTrue(self.quick.findChild(QObject, name).property("checked"))
        self.assertGreaterEqual(self.host.files_dock.y(),
                                self.host.folders_dock.y() + self.host.folders_dock.height())
        self.assertEqual(self.host.geometry(), geometry)
        self.assertTrue(self.controller.enumerateConflicts)
        self.host.tabifyDockWidget(self.host.folders_dock, self.host.files_dock)
        QMetaObject.invokeMethod(menu, "triggered")
        APP.processEvents()
        self.assertEqual(self.host.tabifiedDockWidgets(self.host.folders_dock), [])

    def test_file_quit_closes_native_host(self):
        QMetaObject.invokeMethod(self.quick.findChild(QObject, "quitMenu"), "triggered")
        APP.processEvents()
        self.assertFalse(self.host.isVisible())

    def test_conflict_checkbox_persists_and_controls_worker(self):
        checkbox = self.host.enumerate_conflicts
        self.assertFalse(checkbox.isChecked())
        checkbox.click()
        self.assertTrue(self.controller.enumerateConflicts)
        self.assertTrue(Controller().enumerateConflicts)
        with patch.object(self.controller, "_launch") as launch:
            self.controller.start()
            self.assertIn("--enumerate-conflicts", launch.call_args.args[1])
            checkbox.click()
            self.controller.start(0)
            self.assertNotIn("--enumerate-conflicts", launch.call_args.args[1])
        self.assertFalse(Controller().enumerateConflicts)
        self.controller.enumerateConflicts = True
        self.assertTrue(checkbox.isChecked())

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
        self.quick.setProperty("font", font)
        self.host.resize(900, 600)
        APP.processEvents()
        for field in [*self.host.folder_fields.values(), *self.host.file_fields.values()]:
            self.assertGreaterEqual(field.height(), field.sizeHint().height())
            self.assertGreaterEqual(field.width(), field.minimumSizeHint().width())
        scroll = self.host.folders_dock.widget()
        self.assertTrue(scroll.widgetResizable())
        self.assertGreaterEqual(self.quick.width(), 640)
        pending = [self.quick.contentItem()]
        controls = {}
        while pending:
            item = pending.pop()
            controls[item.objectName()] = item
            pending.extend(item.childItems())
        for name in ("executeRules", "checkAll", "pauseProcessing", "stopProcessing", "cancelProcessing",
                     "openOutputFolder", "copyOutput"):
            button = controls[name]
            position = button.mapToScene(QPointF(0, 0))
            self.assertGreaterEqual(position.x(), 0, name)
            self.assertLessEqual(position.x() + button.width(), self.quick.width(), name)
            self.assertLessEqual(position.y() + button.height(), self.quick.height(), name)

    def test_rule_columns_remain_readable_in_narrow_window(self):
        self.host.resize(900, 600)
        APP.processEvents()
        scroll = self.quick.findChild(QObject, "settingsScroll")
        self.assertGreater(scroll.property("contentWidth"), scroll.property("availableWidth"))
        expected_media = {"landscape": "video", "extension": "other", "rename_images": "image",
                          "rename_videos": "video", "photo_extensions": "image", "video_extensions": "video",
                          "remove_empty_dirs": "other", "landscape_images": "image", "data_extensions": "other"}
        pending = [self.quick.contentItem()]
        controls = {}
        while pending:
            item = pending.pop()
            controls[item.objectName()] = item
            pending.extend(item.childItems())
        for rule_id, media in expected_media.items():
            name = controls[rule_id + "Enabled"]
            self.assertGreaterEqual(name.width(), name.implicitWidth())
            media_label = controls[rule_id + "MediaType"]
            self.assertEqual(media_label.property("text"), media)
            self.assertLess(controls[rule_id + "RuleType"].x(), media_label.x())
            self.assertLess(media_label.x(), name.x())
        for rule_id in ("photo_extensions", "video_extensions", "data_extensions"):
            self.assertEqual(controls[rule_id + "RuleType"].property("text"), "file")

    def test_layout_restores_in_fresh_process_after_close_and_restart(self):
        script = r"""
import json, sys
from pathlib import Path
from PySide6.QtCore import QObject, QTimer, Qt, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from folderconformer import app
qt = QApplication([])
app.user_config_path = lambda *a, **k: Path(sys.argv[1])
controller = app.Controller()
engine = QQmlApplicationEngine()
engine.setInitialProperties({"controller": controller, "visible": False})
engine.load(QUrl.fromLocalFile(str(Path(app.__file__).parent / "qml/Main.qml")))
quick = engine.rootObjects()[0]
host = app.MainWindow(controller, quick)
host.show()
result = {}
def inspect():
    if sys.argv[2] == "save":
        host.resize(1200, 800)
        host.move(100, 100)
        if sys.argv[3] == "docked":
            host.addDockWidget(Qt.LeftDockWidgetArea, host.folders_dock)
            host.splitDockWidget(host.folders_dock, host.files_dock, Qt.Vertical)
            host.resizeDocks([host.folders_dock], [340], Qt.Horizontal)
            host.resizeDocks([host.folders_dock, host.files_dock], [450, 300], Qt.Vertical)
        else:
            for index, dock in enumerate((host.folders_dock, host.files_dock)):
                dock.setFloating(True)
                dock.setGeometry(160 + index * 400, 180, 350, 420)
            if sys.argv[3] == "folders_closed":
                host.folders_dock.close()
            if sys.argv[3] == "files_closed":
                host.files_dock.close()
    QTest.qWait(100)
    result["window"] = host.geometry().getRect()
    result["docks"] = [
        [dock.objectName(), host.dockWidgetArea(dock).value, dock.isFloating(),
         dock.isVisible(), dock.geometry().getRect(),
         quick.findChild(QObject, menu).property("checked")]
        for dock, menu in ((host.folders_dock, "foldersMenu"), (host.files_dock, "filesMenu"))
    ]
    if sys.argv[4] == "restart":
        controller.restart()
    else:
        host.close()
QTimer.singleShot(100, inspect)
qt.exec()
print(json.dumps(result))
"""
        for scenario in ("docked", "floating", "folders_closed", "files_closed"):
            for shutdown in ("close", "restart"):
                with self.subTest(scenario=scenario, shutdown=shutdown):
                    with tempfile.TemporaryDirectory() as directory:
                        saved = subprocess.run(
                            [sys.executable, "-c", script, directory, "save", scenario, shutdown],
                            check=True, capture_output=True, text=True, timeout=15)
                        restored = subprocess.run(
                            [sys.executable, "-c", script, directory, "restore", scenario, "close"],
                            check=True, capture_output=True, text=True, timeout=15)
                        self.assertEqual(json.loads(restored.stdout), json.loads(saved.stdout))
