import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QEvent, QEventLoop, QObject, QPointF, QSettings, QTimer, Qt, QUrl
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
                position = item.mapToScene(QPointF(0, 0))
                scroll.setProperty("contentY", max(0, scroll.property("contentY") + position.y() - 100))
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
                            ("configFolder", str(Path(self.temporary.name) / "settings é")),
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
        self.assertEqual(restored.configFolder, str(Path(self.temporary.name) / "settings é"))
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
        for name in ("landscapeFolder", "configFolder", "videoFolder", "imageFolder"):
            self.assertIsNotNone(panels[1].findChild(QObject, name))
        checkbox = window.findChild(QObject, "includeSubdirectories")
        self.assertFalse(checkbox.property("checked"))
        position = checkbox.mapToScene(QPointF(checkbox.width() / 2, checkbox.height() / 2)).toPoint()
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, position)
        self.assertTrue(controller.includeSubdirectories)
        self.assertTrue(Controller().includeSubdirectories)
        self.assertEqual(messages, [])
        window.close()
