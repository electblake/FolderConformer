import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Q_ARG, QEvent, QEventLoop, QMetaObject, QObject, QPointF, QSettings, QTimer, Qt, QUrl
from PySide6.QtGui import QGuiApplication, QKeyEvent
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

from folderconformer.app import Controller


APP = QGuiApplication.instance() or QGuiApplication([])
APP.setOrganizationName("FolderConformerTests")
APP.setApplicationName("FolderConformerTests")


class SettingsUiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.config_folder = Path(self.temporary.name) / "config"
        config_path = patch("folderconformer.app.user_config_path", return_value=self.config_folder)
        self.config_path = config_path.start()
        self.addCleanup(config_path.stop)

    def rule_control(self, window, name):
        pending = [window.contentItem()]
        while pending:
            item = pending.pop()
            if item.objectName() == name:
                scroll = window.findChild(QObject, "settingsScroll").property("contentItem")
                if scroll.isAncestorOf(item):
                    position = item.mapToItem(scroll, QPointF(0, 0))
                    scroll.setProperty("contentY", max(0, scroll.property("contentY") + position.y()))
                APP.processEvents()
                return item
            pending.extend(item.childItems())

    def test_new_folder_rules_can_move_down_and_disable(self):
        controller = Controller()
        engine = QQmlApplicationEngine()
        engine.setInitialProperties({"controller": controller})
        engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
        window = engine.rootObjects()[0]
        APP.processEvents()
        window.requestActivate()
        self.assertTrue(QTest.qWaitForWindowActive(window))
        self.assertFalse(self.rule_control(window, "landscapeMoveUp").property("enabled"))
        self.assertFalse(self.rule_control(window, "video_extensionsMoveDown").property("enabled"))
        for name in ("rename_imagesMoveDown", "rename_imagesEnabled"):
            QTest.qWait(30)
            control = self.rule_control(window, name)
            position = control.mapToScene(QPointF(control.width() / 2, control.height() / 2)).toPoint()
            QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, position)
            APP.processEvents()
        self.assertEqual(controller.rules[3], {"id": "rename_images", "enabled": False})
        self.assertEqual(Controller().rules, controller.rules)
        window.close()

    def test_platformdirs_config_location(self):
        controller = Controller()
        self.config_path.assert_called_once_with("FolderConformer", appauthor=False)
        self.assertEqual(Path(controller.settings.fileName()), self.config_folder / "FolderConformer.ini")
        self.assertEqual(controller.settings.format(), QSettings.Format.IniFormat)
        self.assertFalse(controller.settings.fallbacksEnabled())
        self.assertEqual(controller.configFolder, str(self.config_folder))
        self.assertEqual(controller.videoFolder, "video/")
        self.assertEqual(controller.imageFolder, "photo/")
        self.assertEqual(controller.videoExtensions,
                         "mp4;ts;m4v;wmv;avi;mov;mkv;webm;mpg;mpeg;mts;m2ts;m2v;vob;flv;3gp;3g2;ogv;asf")
        self.assertEqual(controller.imageExtensions, "jpg;jpeg;png;webp;heic")

    def test_all_control_values_restore_in_fresh_process(self):
        controller = Controller()
        controller.selectFolder(QUrl.fromLocalFile(r"C:\media\日本語 é"))
        controller.landscapeFolder = "Paysage é"
        controller.videoFolder = "Clips/"
        controller.imageFolder = "Pictures/"
        controller.videoExtensions = "mxf;mp4"
        controller.imageExtensions = "gif;png"
        controller.selectConfigFolder(QUrl.fromLocalFile(str(Path(self.temporary.name) / "custom config")))
        controller.includeSubdirectories = True
        for index in range(len(controller.rules)):
            controller.setEnabled(index, False)
        controller.moveRule(1, -1)
        read_script = (
            "import json,sys; from pathlib import Path; from PySide6.QtCore import QCoreApplication; "
            "from folderconformer import app; qt=QCoreApplication([]); "
            "app.user_config_path=lambda *a,**k:Path(sys.argv[1]); c=app.Controller(); "
            "print(json.dumps([c.folder,c.landscapeFolder,c.includeSubdirectories,c.rules,"
            "c.videoFolder,c.imageFolder,c.videoExtensions,c.imageExtensions,c.configFolder]))"
        )
        result = subprocess.run([sys.executable, "-c", read_script, str(self.config_folder)],
                                check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout), [
            controller.folder, "Paysage é", True,
            controller.rules,
            "Clips/", "Pictures/", "mxf;mp4", "gif;png", controller.configFolder,
        ])
        self.assertEqual(controller.settings.status(), QSettings.Status.NoError)

    def test_controller_runs_worker_and_reports_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "日本語"
            folder.mkdir()
            (folder / "é.txt").write_text("content")
            controller = Controller()
            controller.folder = str(folder)
            controller._rules = [{"id": "extension", "enabled": True}]
            loop = QEventLoop()
            results = []
            progress = []
            controller.completed.connect(lambda code: (results.append(code), loop.quit()))
            controller.progress.connect(lambda *event: progress.append(event))
            controller.start()
            QTimer.singleShot(10000, loop.quit)
            loop.exec()
            self.assertEqual(results, [0])
            self.assertEqual(progress[0][:2], (1, 1))
            self.assertTrue((folder / "txt/é.txt").is_file())
            self.assertFalse(controller.running)

    def test_folder_progress_and_summary_reach_completion_status(self):
        folder = Path(self.temporary.name) / "media"
        (folder / "Images").mkdir(parents=True)
        (folder / "Videos").mkdir()
        (folder / "GIF").mkdir()
        (folder / "mxf").mkdir()
        controller = Controller()
        controller.folder = str(folder)
        controller.videoFolder = "Clips/"
        controller.imageFolder = "Pictures/"
        controller.videoExtensions = "mxf"
        controller.imageExtensions = "gif"
        controller._rules = [{"id": rule_id, "enabled": True} for rule_id in
                             ("rename_images", "rename_videos", "photo_extensions", "video_extensions", "extension")]
        engine = QQmlApplicationEngine()
        engine.setInitialProperties({"controller": controller})
        engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
        window = engine.rootObjects()[0]
        loop = QEventLoop()
        results = []
        progress = []
        summaries = []
        controller.progress.connect(lambda *event: progress.append(event))
        controller.completionSummary.connect(summaries.append)
        controller.completed.connect(lambda code: (results.append(code), loop.quit()))
        controller.start()
        QTimer.singleShot(10000, loop.quit)
        loop.exec()
        self.assertEqual(results, [0])
        self.assertEqual([event[:2] for event in progress], [(1, 1)] * 4)
        for name in ("Pictures/GIF", "Clips/mxf"):
            self.assertTrue((folder / name).is_dir())
        summary = "0 files processed, 0 files moved, 2 folders renamed, 2 folders moved."
        self.assertEqual(summaries, [summary])
        screen = window.findChild(QObject, "conformerScreen")
        self.assertEqual(screen.property("status"), "Complete: " + summary)
        window.close()

    def test_controller_passes_recursive_option_to_worker(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "nested/deep").mkdir(parents=True)
            (folder / "nested/deep/note.txt").write_text("nested content")
            controller = Controller()
            controller.folder = str(folder)
            controller.includeSubdirectories = True
            controller._rules = [{"id": "extension", "enabled": True}]
            loop = QEventLoop()
            results = []
            controller.completed.connect(lambda code: (results.append(code), loop.quit()))
            controller.start()
            QTimer.singleShot(10000, loop.quit)
            loop.exec()
            self.assertEqual(results, [0])
            self.assertEqual((folder / "txt/note.txt").read_text(), "nested content")
            self.assertFalse(controller.running)

    def test_settings_and_rules_round_trip(self):
        first = Controller()
        self.assertFalse(first.includeSubdirectories)
        first.folder = r"C:\media\日本語 é"
        first.includeSubdirectories = True
        first.landscapeFolder = "Wide media"
        first.setEnabled(0, False)
        first.moveRule(0, 1)
        second = Controller()
        self.assertEqual(second.folder, first.folder)
        self.assertTrue(second.includeSubdirectories)
        self.assertEqual(second.landscapeFolder, "Wide media")
        self.assertEqual(second.rules, [{"id": "extension", "enabled": True}, {"id": "landscape", "enabled": False}]
                                 + [{"id": rule_id, "enabled": True} for rule_id in
                                    ("rename_images", "rename_videos", "photo_extensions", "video_extensions")])
        second.moveRule(5, -1)
        second.setEnabled(4, False)
        self.assertEqual(Controller().rules, second.rules)
        self.assertFalse(second.settings.fallbacksEnabled())
        second.includeSubdirectories = False
        self.assertFalse(Controller().includeSubdirectories)

    def test_ui_edits_save_automatically_and_restore(self):
        controller = Controller()
        rule_ids = [rule["id"] for rule in controller.rules]
        qml = QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml"))
        engine = QQmlApplicationEngine()
        engine.setInitialProperties({"controller": controller})
        engine.load(qml)
        window = engine.rootObjects()[0]
        APP.processEvents()
        for name, value in (("inputFolder", r"C:\media\日本語 é"), ("landscapeFolder", "Wide media é"),
                            ("videoFolder", "Clips/"), ("imageFolder", "Pictures/"),
                            ("videoExtensions", "mxf;mp4"), ("imageExtensions", "gif;png")):
            field = window.findChild(QObject, name)
            field.forceActiveFocus()
            QTest.keyClick(window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            APP.sendEvent(window, QKeyEvent(QEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, value))
            APP.processEvents()
            self.assertEqual(field.property("text"), value)
        for name in ["includeSubdirectories", *[rule_id + "Enabled" for rule_id in rule_ids], "extensionMoveUp"]:
            QTest.qWait(30)
            control = self.rule_control(window, name)
            position = control.mapToScene(QPointF(control.width() / 2, control.height() / 2)).toPoint()
            QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, position)
            APP.processEvents()
        window.close()
        restored = Controller()
        restored_engine = QQmlApplicationEngine()
        restored_engine.setInitialProperties({"controller": restored})
        restored_engine.load(qml)
        restored_window = restored_engine.rootObjects()[0]
        self.assertEqual(restored_window.findChild(QObject, "inputFolder").property("text"), r"C:\media\日本語 é")
        self.assertEqual(restored_window.findChild(QObject, "landscapeFolder").property("text"), "Wide media é")
        self.assertEqual(Path(restored.settings.fileName()), Path(restored.configFolder) / "FolderConformer.ini")
        for name, value in (("videoFolder", "Clips/"), ("imageFolder", "Pictures/"),
                            ("videoExtensions", "mxf;mp4"), ("imageExtensions", "gif;png")):
            self.assertEqual(restored_window.findChild(QObject, name).property("text"), value)
        self.assertTrue(restored_window.findChild(QObject, "includeSubdirectories").property("checked"))
        for rule_id in rule_ids:
            self.assertFalse(self.rule_control(restored_window, rule_id + "Enabled").property("checked"))
        self.assertEqual(restored.rules, [{"id": rule_id, "enabled": False} for rule_id in
                                         [rule_ids[1], rule_ids[0], *rule_ids[2:]]])
        restored_window.close()

    def test_settings_dialog_saves_theme_and_moves_configuration(self):
        controller = Controller()
        controller.folder = str(Path(self.temporary.name) / "media")
        engine = QQmlApplicationEngine()
        messages = []
        engine.warnings.connect(lambda warnings: messages.extend(warning.toString() for warning in warnings))
        engine.setInitialProperties({"controller": controller})
        engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
        window = engine.rootObjects()[0]
        menu = window.findChild(QObject, "settingsMenu")
        QMetaObject.invokeMethod(menu, "triggered")
        APP.processEvents()
        dialog = window.findChild(QQuickWindow, "settingsDialog")
        self.assertTrue(dialog.isVisible())
        self.assertIsNone(window.findChild(QObject, "ruleFoldersPanel").findChild(QObject, "configFolder"))
        selector = dialog.findChild(QObject, "themeSelector")
        self.assertEqual(selector.property("currentText"), "blender")
        selector.setProperty("currentIndex", controller.themes.index("nord"))
        QMetaObject.invokeMethod(selector, "activated", Q_ARG(int, selector.property("currentIndex")))
        self.assertEqual(controller.theme, "nord")
        field = dialog.findChild(QObject, "configFolder")
        destination = str(Path(self.temporary.name) / "settings é")
        field.setProperty("text", destination)
        QMetaObject.invokeMethod(field, "editingFinished")
        restored = Controller()
        self.assertEqual(restored.configFolder, destination)
        self.assertEqual(restored.theme, "nord")
        self.assertEqual(restored.folder, controller.folder)
        self.assertEqual(restored.settings.value("appearance/theme"), "nord")
        self.assertEqual(restored.settings.status(), QSettings.Status.NoError)
        read_script = (
            "import json,sys; from pathlib import Path; from PySide6.QtCore import QCoreApplication; "
            "from folderconformer import app; qt=QCoreApplication([]); "
            "app.user_config_path=lambda *a,**k:Path(sys.argv[1]); c=app.Controller(); "
            "print(json.dumps([c.configFolder,c.theme,c.folder]))"
        )
        result = subprocess.run([sys.executable, "-c", read_script, str(self.config_folder)],
                                check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout), [destination, "nord", controller.folder])
        with patch("folderconformer.app.QGuiApplication.quit") as quit_app:
            QMetaObject.invokeMethod(dialog.findChild(QObject, "restartAndApply"), "clicked")
            quit_app.assert_called_once()
        self.assertTrue(controller.restart_requested)
        self.assertEqual(Controller().theme, "nord")
        selector.setProperty("currentIndex", 0)
        QMetaObject.invokeMethod(selector, "activated", Q_ARG(int, 0))
        self.assertEqual(Controller().theme, "")
        QMetaObject.invokeMethod(dialog.findChild(QObject, "closeSettings"), "clicked")
        self.assertFalse(dialog.isVisible())
        QMetaObject.invokeMethod(menu, "triggered")
        self.assertTrue(dialog.isVisible())
        self.assertEqual(messages, [])
        window.close()
        self.assertFalse(dialog.isVisible())

    def test_theme_colors_reach_rendered_qml_windows(self):
        script = r"""
import json, sys
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QMetaObject, QObject
from PySide6.QtQml import QQmlEngine, QQmlExpression
from PySide6.QtTest import QTest
from folderconformer import app
qt = app.QGuiApplication([])
engine = app.QQmlApplicationEngine()
config = Path(sys.argv[1])
theme = sys.argv[2]
app.user_config_path = lambda *a, **k: config
controller = app.Controller()
controller.theme = theme
colors = []
def inspect():
    window = engine.rootObjects()[0]
    QMetaObject.invokeMethod(window.findChild(QObject, "settingsMenu"), "triggered")
    QTest.qWait(100)
    dialog = window.findChild(QObject, "settingsDialog")
    for obj, expression in ((window, "palette.window.toString()"),
                            (dialog, "palette.window.toString()"),
                            (dialog.findChild(QObject, "configFolder"), "palette.base.toString()"),
                            (dialog.findChild(QObject, "restartAndApply"), "palette.button.toString()")):
        colors.append(QQmlExpression(QQmlEngine.contextForObject(obj), obj, expression).evaluate()[0])
    image = dialog.grabWindow()
    colors.append(image.pixelColor(0, 0).name())
    window.close()
    return 0
with patch.object(app, "QGuiApplication", return_value=qt), patch.object(app, "QQmlApplicationEngine", return_value=engine), patch.object(qt, "exec", side_effect=inspect), patch.object(sys, "argv", ["folderconformer"]):
    app.main()
print(json.dumps(colors))
"""
        import qt_themes
        from PySide6.QtGui import QPalette
        for theme in ("nord", "github_light"):
            with self.subTest(theme=theme):
                result = subprocess.run([sys.executable, "-c", script, str(self.config_folder), theme],
                                        check=True, capture_output=True, text=True, timeout=15)
                palette = QPalette()
                qt_themes.update_palette(palette, qt_themes.get_themes()[theme])
                self.assertEqual(json.loads(result.stdout), [palette.window().color().name(),
                    palette.window().color().name(), palette.base().color().name(),
                    palette.button().color().name(), palette.window().color().name()])

    def test_qml_loads(self):
        controller = Controller()
        controller.includeSubdirectories = False
        engine = QQmlApplicationEngine()
        messages = []
        engine.warnings.connect(lambda warnings: messages.extend(warning.toString() for warning in warnings))
        engine.setInitialProperties({"controller": controller})
        engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
        self.assertEqual(len(engine.rootObjects()), 1)
        window = engine.rootObjects()[0]
        APP.processEvents()
        panels = [window.findChild(QQuickItem, name) for name in ("rulesPanel", "ruleFoldersPanel", "filesPanel")]
        for upper, lower in zip(panels, panels[1:]):
            self.assertLessEqual(upper.y() + upper.height(), lower.y())
        for name in ("landscapeFolder", "videoFolder", "imageFolder"):
            self.assertIsNotNone(panels[1].findChild(QObject, name))
        checkbox = window.findChild(QObject, "includeSubdirectories")
        self.assertFalse(checkbox.property("checked"))
        position = checkbox.mapToScene(QPointF(checkbox.width() / 2, checkbox.height() / 2)).toPoint()
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, position)
        self.assertTrue(controller.includeSubdirectories)
        self.assertTrue(Controller().includeSubdirectories)
        self.assertEqual(messages, [])
        window.close()

    def test_file_menu_selects_input_folder_and_quits(self):
        APP.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
        self.addCleanup(lambda: APP.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, False))
        controller = Controller()
        engine = QQmlApplicationEngine()
        messages = []
        engine.warnings.connect(lambda warnings: messages.extend(warning.toString() for warning in warnings))
        engine.setInitialProperties({"controller": controller})
        engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
        window = engine.rootObjects()[0]
        select = window.findChild(QObject, "selectFolderMenu")
        quit_menu = window.findChild(QObject, "quitMenu")
        screen = window.findChild(QObject, "conformerScreen")
        controller.updates._busy = True
        controller.updates.changed.emit()
        self.assertFalse(select.property("enabled"))
        self.assertFalse(quit_menu.property("enabled"))
        controller.updates._busy = False
        controller.updates.changed.emit()
        self.assertTrue(select.property("enabled"))
        self.assertTrue(quit_menu.property("enabled"))
        QMetaObject.invokeMethod(select, "triggered")
        APP.processEvents()
        dialog = next(child for child in window.findChildren(QObject)
                      if child.property("title") == "Select input folder")
        QMetaObject.invokeMethod(dialog, "reject")
        APP.processEvents()
        APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(screen.property("choosingFolder"))
        self.assertEqual(controller.folder, "")
        QMetaObject.invokeMethod(select, "triggered")
        APP.processEvents()
        dialog = next(child for child in window.findChildren(QObject)
                      if child.property("title") == "Select input folder")
        folder = Path(self.temporary.name) / "日本語 é"
        folder.mkdir()
        dialog.setProperty("selectedFolder", QUrl.fromLocalFile(str(folder)))
        QMetaObject.invokeMethod(dialog, "accept")
        APP.processEvents()
        self.assertFalse(screen.property("choosingFolder"))
        self.assertEqual(Path(controller.folder), folder)
        self.assertEqual(window.findChild(QObject, "inputFolder").property("text"), controller.folder)
        self.assertEqual(Controller().folder, controller.folder)
        QMetaObject.invokeMethod(quit_menu, "triggered")
        APP.processEvents()
        self.assertFalse(window.isVisible())
        self.assertEqual(messages, [])

    def test_processing_pause_resume_stop_and_cancel(self):
        for action in ("resume", "stop", "cancel"):
            with self.subTest(action=action):
                folder = Path(self.temporary.name) / action
                folder.mkdir()
                (folder / "note.txt").write_text("content")
                controller = Controller()
                controller.folder = str(folder)
                controller._rules = [{"id": "extension", "enabled": True}]
                engine = QQmlApplicationEngine()
                engine.setInitialProperties({"controller": controller})
                engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
                window = engine.rootObjects()[0]
                buttons = [window.findChild(QObject, name) for name in
                           ("pauseProcessing", "stopProcessing", "cancelProcessing")]
                self.assertTrue(all(not button.property("enabled") for button in buttons))
                loop = QEventLoop()
                controller.runStateChanged.connect(lambda: loop.quit() if controller.runState == "paused" else None)
                controller.start()
                controller.pause()
                QTimer.singleShot(5000, loop.quit)
                loop.exec()
                self.assertEqual(controller.runState, "paused")
                self.assertTrue(controller.running)
                self.assertTrue((folder / "note.txt").is_file())
                self.assertEqual(buttons[0].property("text"), "Resume")
                self.assertTrue(all(button.property("enabled") for button in buttons))
                results = []
                controller.completed.connect(lambda code: (results.append(code), loop.quit()))
                if action == "resume":
                    controller.pause()
                elif action == "stop":
                    controller.stop()
                else:
                    controller.cancel()
                QTimer.singleShot(5000, loop.quit)
                loop.exec()
                self.assertEqual(len(results), 1)
                self.assertFalse(controller.running)
                self.assertTrue(all(not button.property("enabled") for button in buttons))
                if action == "resume":
                    self.assertEqual(results, [0])
                    self.assertTrue((folder / "txt/note.txt").is_file())
                else:
                    self.assertEqual(controller.runState, "stopped" if action == "stop" else "cancelled")
                    self.assertTrue((folder / "note.txt").is_file())
                window.close()
