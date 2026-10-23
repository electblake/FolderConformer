import contextlib
import io
import json
import logging
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Q_ARG, QEvent, QEventLoop, QMetaObject, QObject, QPointF, QSettings, QTimer, Qt, QUrl
from PySide6.QtGui import QGuiApplication, QKeyEvent
from PySide6.QtQml import QQmlApplicationEngine, QQmlEngine, QQmlExpression
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from folderconformer.app import StandardIconProvider, Controller, MainWindow
from folderconformer.pipeline import conform
from static_ffmpeg.run import get_platform_dir


APP = QApplication.instance() or QApplication([])
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
                    scroll.setProperty("contentX", max(0, min(scroll.property("contentX") + position.x(),
                                                              scroll.property("contentWidth") - scroll.width())))
                APP.processEvents()
                return item
            pending.extend(item.childItems())

    def test_rule_action_icons_are_loaded_compact_and_accessible(self):
        controller = Controller(self.temporary.name)
        engine = QQmlApplicationEngine()
        engine.addImageProvider("standard", StandardIconProvider())
        messages = []
        engine.warnings.connect(lambda warnings: messages.extend(warning.toString() for warning in warnings))
        engine.setInitialProperties({"controller": controller})
        engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
        window = engine.rootObjects()[0]
        QTest.qWait(100)
        for suffix, icon, label in (("Check", "check", "Check this rule"),
                                    ("RunOnce", "run", "Run this rule once"),
                                    ("MoveUp", "up", "Move rule up"),
                                    ("MoveDown", "down", "Move rule down")):
            with self.subTest(action=suffix):
                button = self.rule_control(window, controller.rules[0]["id"] + suffix)
                self.assertTrue(QQmlExpression(QQmlEngine.contextForObject(button), button,
                                               "display === AbstractButton.IconOnly").evaluate()[0])
                self.assertAlmostEqual(button.width(), button.height(), delta=1)
                self.assertTrue(QQmlExpression(QQmlEngine.contextForObject(button), button,
                                               'icon.width === 16 && icon.height === 16').evaluate()[0])
                if icon == "check":
                    self.assertTrue(QQmlExpression(QQmlEngine.contextForObject(button), button,
                                                   "icon.color.a === 0").evaluate()[0])
                self.assertEqual(QQmlExpression(QQmlEngine.contextForObject(button), button,
                                                "Accessible.name").evaluate()[0], label)
                self.assertEqual(QQmlExpression(QQmlEngine.contextForObject(button), button,
                                                "ToolTip.text").evaluate()[0], label)
                images = [item for item in button.findChildren(QQuickItem)
                          if item.property("source") == QUrl("image://standard/" + icon)]
                self.assertTrue(images)
                self.assertTrue(all(QQmlExpression(QQmlEngine.contextForObject(item), item,
                                                   "status === Image.Ready").evaluate()[0] for item in images))
        self.assertFalse(self.rule_control(window, controller.rules[0]["id"] + "MoveUp").property("enabled"))
        self.assertFalse(self.rule_control(window, controller.rules[-1]["id"] + "MoveDown").property("enabled"))
        self.assertEqual(messages, [])
        window.close()

    def test_check_all_runs_enabled_checks_without_changing_files(self):
        folder = Path(self.temporary.name) / "media"
        folder.mkdir()
        (folder / "note.txt").write_text("content")
        controller = Controller(str(folder))
        controller._rules = [{"id": "remove_empty_dirs", "enabled": True},
                             {"id": "landscape", "enabled": False},
                             {"id": "extension", "enabled": True}]
        engine = QQmlApplicationEngine()
        engine.addImageProvider("standard", StandardIconProvider())
        engine.setInitialProperties({"controller": controller})
        engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
        window = engine.rootObjects()[0]
        APP.processEvents()
        check_all = window.findChild(QObject, "checkAll")
        execute = window.findChild(QObject, "executeRules")
        self.assertEqual(check_all.parentItem(), execute.parentItem())
        self.assertGreater(check_all.x(), execute.x())
        QMetaObject.invokeMethod(check_all, "clicked")
        self.assertTrue(controller.checking)
        self.assertFalse(check_all.property("enabled"))
        self.assertFalse(window.findChild(QObject, "pauseProcessing").property("enabled"))
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(controller.process.exitCode(), 0)
        self.assertEqual(controller.checkStatuses, {"remove_empty_dirs": "OK", "extension": "BAD"})
        self.assertEqual(json.loads(controller.process.arguments()[8]), ["remove_empty_dirs", "extension"])
        self.assertEqual(list(folder.iterdir()), [folder / "note.txt"])
        self.assertEqual((folder / "note.txt").read_text(), "content")
        self.assertTrue(check_all.property("enabled"))
        controller.output.emit("Activity output")
        APP.processEvents()
        log = window.findChild(QQuickItem, "applicationLog")
        self.assertIn("Check: extension BAD", log.property("text"))
        copy = window.findChild(QQuickItem, "copyOutput")
        self.assertGreaterEqual(copy.mapToScene(QPointF(0, 0)).y(),
                                log.mapToScene(QPointF(0, log.height())).y())
        QMetaObject.invokeMethod(copy, "clicked")
        self.assertEqual(APP.clipboard().text(), log.property("text"))
        for index in range(len(controller.rules)):
            controller.setEnabled(index, False)
        self.assertFalse(check_all.property("enabled"))
        window.close()

    def test_worker_logs_include_traceback_and_exit_details(self):
        controller = Controller()
        output = []
        controller.output.connect(output.append)
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(controller.log_handler.formatter)
        logger = logging.getLogger("folderconformer")
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        logging.getLogger("folderconformer.updates").warning("Application warning")
        with patch.object(controller.process, "start"):
            controller._launch("conform", [])
        controller.process.setArguments(["-u", "-c",
            "import sys; print('worker output'); sys.stderr.write('stderr detail\\n'); "
            "raise RuntimeError('actual failure')"])
        controller.process.start()
        self.assertTrue(controller.process.waitForFinished(10000))
        text = "".join(output)
        self.assertEqual(text, stream.getvalue())
        for expected in ("WARNING folderconformer.updates: Application warning", "Starting conform:",
                         "worker output", "stderr detail", "Traceback (most recent call last):",
                         "RuntimeError: actual failure", "exit_code=1 (0x00000001), exit_status=NormalExit"):
            self.assertIn(expected, text)
        self.assertTrue(all(record.endswith("\n") for record in output))

    def test_repeated_crashes_preserve_unterminated_output(self):
        controller = Controller()
        output = []
        controller.output.connect(output.append)
        for _ in range(2):
            with patch.object(controller.process, "start"):
                controller._launch("conform", [])
            controller.process.setArguments(["-u", "-c",
                "import sys,time; sys.stderr.write('unterminated detail'); sys.stderr.flush(); time.sleep(30)"])
            controller.process.start()
            self.assertTrue(controller.process.waitForReadyRead(10000))
            controller.process.kill()
            self.assertTrue(controller.process.waitForFinished(10000))
        text = "".join(output)
        self.assertEqual(text.count("folderconformer.worker: unterminated detail"), 2)
        self.assertEqual(text.count("exit_status=CrashExit"), 2)
        self.assertIn("process error Crashed:", text)
        self.assertTrue(all(record.endswith("\n") for record in output))
        self.assertNotIn("Process crashedProcess crashed", text)

    def test_checks_follow_rule_identity_and_clear_when_input_changes(self):
        folder = Path(self.temporary.name) / "media"
        (folder / "video/mp4").mkdir(parents=True)
        (folder / "video/mp4/clip.mp4").write_text("video")
        controller = Controller(str(folder))
        engine = QQmlApplicationEngine()
        engine.addImageProvider("standard", StandardIconProvider())
        engine.setInitialProperties({"controller": controller})
        engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
        window = engine.rootObjects()[0]
        APP.processEvents()
        self.assertEqual(self.rule_control(window, "video_extensionsCheckStatus").property("text"), "-")
        QMetaObject.invokeMethod(self.rule_control(window, "video_extensionsCheck"), "clicked")
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(self.rule_control(window, "video_extensionsCheckStatus").property("text"), "BAD")
        controller.moveRule(5, -1)
        self.assertEqual(self.rule_control(window, "video_extensionsCheckStatus").property("text"), "BAD")
        (folder / "video/mp4/clip.mp4").rename(folder / "video/clip.mp4")
        QMetaObject.invokeMethod(self.rule_control(window, "video_extensionsCheck"), "clicked")
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(self.rule_control(window, "video_extensionsCheckStatus").property("text"), "OK")
        QMetaObject.invokeMethod(self.rule_control(window, "remove_empty_dirsCheck"), "clicked")
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(self.rule_control(window, "remove_empty_dirsCheckStatus").property("text"), "BAD")
        (folder / "video/mp4").rmdir()
        controller.checkRule("remove_empty_dirs")
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(controller.checkStatuses["remove_empty_dirs"], "OK")
        controller.videoExtensions = "mkv"
        self.assertEqual(controller.checkStatuses, {})
        controller.checkRule("video_extensions")
        self.assertTrue(controller.process.waitForFinished(10000))
        controller.folder = str(folder / "video")
        self.assertEqual(controller.checkStatuses, {})
        window.close()

    def test_image_checks_follow_rule_identity_and_clear_when_input_changes(self):
        folder = Path(self.temporary.name) / "media"
        (folder / "photo/jpg").mkdir(parents=True)
        (folder / "photo/jpg/clip.jpg").write_text("photo")
        controller = Controller(str(folder))
        engine = QQmlApplicationEngine()
        engine.addImageProvider("standard", StandardIconProvider())
        engine.setInitialProperties({"controller": controller})
        engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
        window = engine.rootObjects()[0]
        APP.processEvents()
        self.assertEqual(self.rule_control(window, "photo_extensionsCheckStatus").property("text"), "-")
        QMetaObject.invokeMethod(self.rule_control(window, "photo_extensionsCheck"), "clicked")
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(self.rule_control(window, "photo_extensionsCheckStatus").property("text"), "BAD")
        controller.moveRule(4, -1)
        self.assertEqual(self.rule_control(window, "photo_extensionsCheckStatus").property("text"), "BAD")
        (folder / "photo/jpg/clip.jpg").rename(folder / "photo/clip.jpg")
        QMetaObject.invokeMethod(self.rule_control(window, "photo_extensionsCheck"), "clicked")
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(self.rule_control(window, "photo_extensionsCheckStatus").property("text"), "OK")
        QMetaObject.invokeMethod(self.rule_control(window, "remove_empty_dirsCheck"), "clicked")
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(self.rule_control(window, "remove_empty_dirsCheckStatus").property("text"), "BAD")
        (folder / "photo/jpg").rmdir()
        controller.checkRule("remove_empty_dirs")
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(controller.checkStatuses["remove_empty_dirs"], "OK")
        controller.imageExtensions = "png"
        self.assertEqual(controller.checkStatuses, {})
        controller.checkRule("photo_extensions")
        self.assertTrue(controller.process.waitForFinished(10000))
        controller.folder = str(folder / "photo")
        self.assertEqual(controller.checkStatuses, {})
        window.close()

    def test_landscape_check_buttons_sample_configured_destination(self):
        folder = Path(self.temporary.name) / "media"
        folder.mkdir()
        controller = Controller(str(folder))
        controller.videoFolder = "Clips/"
        controller.imageFolder = "Pictures/"
        controller.landscapeFolder = "Wide"
        tools = Path(get_platform_dir())
        engine = QQmlApplicationEngine()
        engine.addImageProvider("standard", StandardIconProvider())
        engine.setInitialProperties({"controller": controller})
        engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
        window = engine.rootObjects()[0]
        for rule_id, directory, suffix in (("landscape", "Clips", "mp4"),
                                           ("landscape_images", "Pictures", "png")):
            with self.subTest(rule=rule_id):
                target = folder / directory / "Wide"
                button = self.rule_control(window, rule_id + "Check")
                status = self.rule_control(window, rule_id + "CheckStatus")
                QMetaObject.invokeMethod(button, "clicked")
                self.assertTrue(controller.process.waitForFinished(10000))
                self.assertEqual(status.property("text"), "BAD")
                target.mkdir(parents=True)
                QMetaObject.invokeMethod(button, "clicked")
                self.assertTrue(controller.process.waitForFinished(10000))
                self.assertEqual(status.property("text"), "BAD")
                (target.parent / f"unprobed.{suffix}").write_text("invalid media outside destination")
                for size, expected in (("80x40", "OK"), ("40x40", "OK"), ("40x80", "BAD")):
                    subprocess.run([str(tools / "ffmpeg.exe"), "-y", "-v", "error", "-f", "lavfi", "-i",
                                    f"color=c=red:s={size}:d=0.1", "-frames:v", "1", str(target / f"sample.{suffix}")],
                                   check=True, capture_output=True)
                    QMetaObject.invokeMethod(button, "clicked")
                    self.assertTrue(controller.process.waitForFinished(10000))
                    self.assertEqual(controller.process.exitCode(), 0)
                    self.assertEqual(status.property("text"), expected)
        controller.setEnabled(next(i for i, rule in enumerate(controller.rules) if rule["id"] == "music_videos"), False)
        controller.checkAll()
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(controller.process.exitCode(), 0)
        self.assertEqual(controller.checkStatuses["landscape"], "BAD")
        self.assertEqual(controller.checkStatuses["landscape_images"], "BAD")
        window.close()

    def test_extension_check_reports_loose_files_and_skipped_conflicts(self):
        folder = Path(self.temporary.name) / "media"
        (folder / "txt").mkdir(parents=True)
        (folder / "txt/note.txt").write_text("existing")
        controller = Controller(str(folder))
        controller.checkRule("extension")
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(controller.checkStatuses["extension"], "OK")
        (folder / "note.txt").write_text("incoming")
        (folder / "no-suffix").write_text("loose")
        controller.checkRule("extension")
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(controller.checkStatuses["extension"], "BAD")
        for enumerate_conflicts, expected in ((False, "BAD"), (True, "OK")):
            with contextlib.redirect_stdout(io.StringIO()):
                conform(folder, [{"id": "extension", "enabled": True}], "Wide", Path("unused"),
                        "video/", "photo/", "mp4", "png", "Data/", "csv;db;txt;", enumerate_conflicts=enumerate_conflicts)
            controller.checkRule("extension")
            self.assertTrue(controller.process.waitForFinished(10000))
            self.assertEqual(controller.checkStatuses["extension"], expected)
        self.assertEqual((folder / "txt/note.txt").read_text(), "existing")
        self.assertEqual((folder / "txt/note_1.txt").read_text(), "incoming")

    def test_rename_check_buttons_match_root_names_and_configured_destinations(self):
        for rule_id, field, source_name, destination in (
                ("rename_images", "imageFolder", "IMAGES", "Pictures/"),
                ("rename_videos", "videoFolder", "VIDEOS", "Clips/")):
            with self.subTest(rule=rule_id):
                folder = Path(self.temporary.name) / rule_id
                (folder / "nested" / source_name).mkdir(parents=True)
                (folder / (source_name + "-backup")).mkdir()
                controller = Controller(str(folder))
                setattr(controller, field, destination)
                engine = QQmlApplicationEngine()
                engine.addImageProvider("standard", StandardIconProvider())
                engine.setInitialProperties({"controller": controller})
                engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
                window = engine.rootObjects()[0]
                button = self.rule_control(window, rule_id + "Check")
                status = self.rule_control(window, rule_id + "CheckStatus")
                self.assertTrue(button.property("enabled"))
                QMetaObject.invokeMethod(button, "clicked")
                self.assertTrue(controller.process.waitForFinished(10000))
                self.assertEqual(status.property("text"), "BAD")
                (folder / source_name).mkdir()
                (folder / destination).mkdir()
                QMetaObject.invokeMethod(button, "clicked")
                self.assertTrue(controller.process.waitForFinished(10000))
                self.assertEqual(status.property("text"), "BAD")
                (folder / destination).rmdir()
                (folder / source_name).rename(folder / destination)
                QMetaObject.invokeMethod(button, "clicked")
                self.assertTrue(controller.process.waitForFinished(10000))
                self.assertEqual(status.property("text"), "OK")
                setattr(controller, field, source_name + "/")
                (folder / destination).rename(folder / source_name)
                controller.checkRule(rule_id)
                self.assertTrue(controller.process.waitForFinished(10000))
                self.assertEqual(controller.checkStatuses[rule_id], "OK")
                window.close()

    def test_checks_run_without_blocking_or_emitting_execution_completion(self):
        folder = Path(self.temporary.name) / "media"
        folder.mkdir()
        controller = Controller(str(folder))
        completed = []
        ticks = []
        controller.completed.connect(completed.append)
        loop = QEventLoop()
        controller.process.finished.connect(loop.quit)
        timer = QTimer()
        timer.setInterval(1)
        timer.timeout.connect(lambda: ticks.append(True))
        timer.start()
        controller.checkRule("extension")
        self.assertTrue(controller.running)
        self.assertTrue(controller.checking)
        self.assertEqual(controller.checkStatuses["extension"], "-")
        QTimer.singleShot(10000, loop.quit)
        loop.exec()
        timer.stop()
        self.assertFalse(controller.running)
        self.assertTrue(ticks)
        self.assertEqual(completed, [])
        self.assertEqual(controller.checkStatuses["extension"], "OK")
        controller.landscapeFolder = "Wide"
        self.assertEqual(controller.checkStatuses, {})

    def test_failed_check_clears_previous_result_and_surfaces_worker_failure(self):
        folder = Path(self.temporary.name) / "media"
        (folder / "photo" / "Landscape-FULL").mkdir(parents=True)
        controller = Controller(str(folder))
        controller.checkRule("landscape_images")
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(controller.checkStatuses["landscape_images"], "BAD")
        (folder / "photo" / "Landscape-FULL" / "broken.png").write_text("invalid image")
        output = []
        controller.output.connect(output.append)
        controller.checkRule("landscape_images")
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertNotEqual(controller.process.exitCode(), 0)
        self.assertIn("Traceback (most recent call last):", "".join(output))
        self.assertEqual(controller.checkStatuses["landscape_images"], "ERR")
        (folder / "photo" / "Landscape-FULL" / "broken.png").unlink()
        controller.checkRule("landscape_images")
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(controller.checkStatuses["landscape_images"], "BAD")

    def test_check_worker_start_failure_reports_err(self):
        controller = Controller(self.temporary.name)
        output = []
        controller.output.connect(output.append)
        with patch("folderconformer.app.sys.executable", str(Path(self.temporary.name) / "python.exe")):
            controller.checkRule("extension")
            self.assertFalse(controller.process.waitForStarted(10000))
        self.assertEqual(controller.checkStatuses["extension"], "ERR")
        self.assertIn(controller.process.errorString(), "".join(output))
        self.assertFalse(controller.running)

    def test_missing_input_folder_reports_err_for_landscape_checks(self):
        controller = Controller(str(Path(self.temporary.name) / "missing"))
        for rule_id in ("landscape", "landscape_images"):
            with self.subTest(rule=rule_id):
                controller.checkRule(rule_id)
                self.assertTrue(controller.process.waitForFinished(10000))
                self.assertNotEqual(controller.process.exitCode(), 0)
                self.assertEqual(controller.checkStatuses[rule_id], "ERR")

    def test_landscape_checks_report_missing_media_folders_as_bad(self):
        folder = Path(self.temporary.name) / "media"
        folder.mkdir()
        controller = Controller(str(folder))
        controller.imageFolder = "pictures"
        controller.videoFolder = "clips"
        for rule_id, directory in (("landscape_images", "pictures"), ("landscape", "clips")):
            with self.subTest(rule=rule_id):
                output = []
                controller.output.connect(output.append)
                controller.checkRule(rule_id)
                self.assertTrue(controller.process.waitForFinished(10000))
                self.assertEqual(controller.process.exitCode(), 0)
                self.assertEqual(controller.checkStatuses[rule_id], "BAD")
                self.assertNotIn("Traceback", "".join(output))
                self.assertFalse((folder / directory).exists())
                (folder / directory).mkdir()
                controller.checkRule(rule_id)
                self.assertTrue(controller.process.waitForFinished(10000))
                self.assertEqual(controller.checkStatuses[rule_id], "BAD")

    def test_new_rule_is_added_to_saved_rules_once(self):
        controller = Controller()
        controller._rules = [{"id": "video_extensions", "enabled": False}, {"id": "extension", "enabled": True}]
        controller.save()
        restored = Controller()
        self.assertEqual(restored.rules, controller.rules + [{"id": "remove_empty_dirs", "enabled": False},
                                                                  {"id": "landscape_images", "enabled": True},
                                                                  {"id": "data_extensions", "enabled": True},
                                                                  {"id": "music_videos", "enabled": True},
                                                                  {"id": "flatten_videos", "enabled": False},
                                                                  {"id": "flatten_images", "enabled": False},
                                                                  {"id": "non_video_to_root", "enabled": True},
                                                                  {"id": "non_image_to_root", "enabled": True}])
        restored.setEnabled(2, False)
        restored.moveRule(2, -1)
        self.assertEqual(Controller().rules, restored.rules)

    def test_new_folder_rules_can_move_down_and_disable(self):
        controller = Controller()
        engine = QQmlApplicationEngine()
        engine.addImageProvider("standard", StandardIconProvider())
        engine.setInitialProperties({"controller": controller})
        engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
        window = engine.rootObjects()[0]
        APP.processEvents()
        window.requestActivate()
        self.assertTrue(QTest.qWaitForWindowActive(window))
        self.assertFalse(self.rule_control(window, "landscapeMoveUp").property("enabled"))
        self.assertFalse(self.rule_control(window, "non_image_to_rootMoveDown").property("enabled"))
        for name in ("rename_imagesMoveDown", "rename_imagesEnabled"):
            QTest.qWait(30)
            control = self.rule_control(window, name)
            position = control.mapToScene(QPointF(control.width() / 2, control.height() / 2)).toPoint()
            QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, position)
            APP.processEvents()
        self.assertEqual(controller.rules[3], {"id": "rename_images", "enabled": False})
        self.assertEqual(Controller().rules, controller.rules)
        window.close()

    def test_run_once_runs_only_selected_disabled_rule_after_reordering(self):
        folder = Path(self.temporary.name) / "media"
        (folder / "images").mkdir(parents=True)
        (folder / "nested").mkdir()
        (folder / "nested/note.txt").write_text("content")
        (folder / "note.txt").write_text("loose file")
        controller = Controller()
        controller.setEnabled(1, False)
        controller.moveRule(1, -1)
        saved_rules = json.loads(json.dumps(controller.rules))
        engine = QQmlApplicationEngine()
        engine.addImageProvider("standard", StandardIconProvider())
        engine.setInitialProperties({"controller": controller})
        engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
        window = engine.rootObjects()[0]
        APP.processEvents()
        for rule in controller.rules:
            button = self.rule_control(window, rule["id"] + "RunOnce")
            move = self.rule_control(window, rule["id"] + "MoveUp")
            self.assertEqual(button.property("text"), "Run Once")
            self.assertFalse(button.property("enabled"))
            self.assertLess(button.x(), move.x())
        controller.folder = str(folder)
        button = self.rule_control(window, "extensionRunOnce")
        self.assertTrue(button.property("enabled"))
        screen = window.findChild(QObject, "conformerScreen")
        screen.setProperty("total", 42)
        screen.setProperty("completionSummary", "previous run")
        loop = QEventLoop()
        results = []
        controller.completed.connect(lambda code: (results.append(code), loop.quit()))
        QMetaObject.invokeMethod(button, "clicked")
        self.assertEqual(screen.property("total"), 0)
        self.assertEqual(screen.property("completionSummary"), "")
        self.assertEqual(screen.property("status"), "Processing…")
        self.assertFalse(button.property("enabled"))
        QTimer.singleShot(10000, loop.quit)
        loop.exec()
        self.assertEqual(results, [0])
        self.assertEqual((folder / "txt/note.txt").read_text(), "loose file")
        self.assertEqual((folder / "nested/note.txt").read_text(), "content")
        self.assertTrue((folder / "images").is_dir())
        self.assertEqual(controller.rules, saved_rules)
        self.assertEqual(Controller().rules, saved_rules)
        self.assertTrue(button.property("enabled"))
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
        self.assertEqual(controller.dataFolder, "Data/")
        self.assertEqual(controller.dataExtensions, "csv;db;txt;")
        self.assertEqual(controller.videoExtensions,
                         "mp4;ts;m4v;wmv;avi;mov;mkv;webm;mpg;mpeg;mts;m2ts;m2v;vob;flv;3gp;3g2;ogv;asf")
        self.assertEqual(controller.imageExtensions, "jpg;jpeg;png;webp;heic")

    def test_data_rule_checks_and_run_once_use_custom_settings(self):
        folder = Path(self.temporary.name) / "input"
        folder.mkdir()
        (folder / "catalog.SQLITE").write_text("database")
        (folder / "notes.txt").write_text("notes")
        controller = Controller(str(folder))
        controller.dataFolder = "Records/"
        controller.dataExtensions = " .SQLITE; "
        index = next(i for i, rule in enumerate(controller.rules) if rule["id"] == "data_extensions")
        controller.setEnabled(index, False)
        controller.moveRule(index, -1)
        index -= 1
        controller.checkRule("data_extensions")
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(controller.checkStatuses["data_extensions"], "BAD")
        controller.start(index)
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(controller.process.exitCode(), 0)
        self.assertEqual((folder / "Records/catalog.SQLITE").read_text(), "database")
        self.assertEqual((folder / "notes.txt").read_text(), "notes")
        self.assertFalse(controller.rules[index]["enabled"])
        controller.checkRule("data_extensions")
        self.assertTrue(controller.process.waitForFinished(10000))
        self.assertEqual(controller.checkStatuses["data_extensions"], "OK")
        controller.dataFolder = "Other/"
        self.assertEqual(controller.checkStatuses, {})
        controller.checkRule("data_extensions")
        self.assertTrue(controller.process.waitForFinished(10000))
        controller.dataExtensions = "txt;"
        self.assertEqual(controller.checkStatuses, {})

    def test_all_control_values_restore_in_fresh_process(self):
        controller = Controller()
        controller.selectFolder(QUrl.fromLocalFile(r"C:\media\日本語 é"))
        controller.landscapeFolder = "Paysage é"
        controller.videoFolder = "Clips/"
        controller.imageFolder = "Pictures/"
        controller.videoExtensions = "mxf;mp4"
        controller.imageExtensions = "gif;png"
        controller.dataFolder = "Records/"
        controller.dataExtensions = " .CSV; sqlite; "
        controller.selectConfigFolder(QUrl.fromLocalFile(str(Path(self.temporary.name) / "custom config")))
        for index in range(len(controller.rules)):
            controller.setEnabled(index, False)
        controller.moveRule(1, -1)
        read_script = (
            "import json,sys; from pathlib import Path; from PySide6.QtCore import QCoreApplication; "
            "from folderconformer import app; qt=QCoreApplication([]); "
            "app.user_config_path=lambda *a,**k:Path(sys.argv[1]); c=app.Controller(); "
            "print(json.dumps([c.folder,c.landscapeFolder,c.rules,"
            "c.videoFolder,c.imageFolder,c.videoExtensions,c.imageExtensions,c.dataFolder,c.dataExtensions,c.configFolder]))"
        )
        result = subprocess.run([sys.executable, "-c", read_script, str(self.config_folder)],
                                check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout), [
            controller.folder, "Paysage é",
            controller.rules,
            "Clips/", "Pictures/", "mxf;mp4", "gif;png", "Records/", " .CSV; sqlite; ", controller.configFolder,
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
        engine.addImageProvider("standard", StandardIconProvider())
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
        self.assertEqual([event[:2] for event in progress], [(1, 1)] * 2)
        for name in ("GIF", "mxf"):
            self.assertTrue((folder / name).is_dir())
        summary = "0 files processed, 0 files moved, 2 folders renamed."
        self.assertEqual(summaries, [summary])
        screen = window.findChild(QObject, "conformerScreen")
        self.assertEqual(screen.property("status"), "Complete: " + summary)
        window.close()

    def test_worker_ignores_old_recursive_setting_and_only_groups_loose_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "nested/deep").mkdir(parents=True)
            (folder / "nested/deep/note.txt").write_text("nested content")
            controller = Controller()
            controller.folder = str(folder)
            controller.settings.setValue("includeSubdirectories", True)
            controller.settings.sync()
            controller = Controller()
            (folder / "root.txt").write_text("root content")
            controller._rules = [{"id": "extension", "enabled": True}]
            loop = QEventLoop()
            results = []
            controller.completed.connect(lambda code: (results.append(code), loop.quit()))
            controller.start()
            QTimer.singleShot(10000, loop.quit)
            loop.exec()
            self.assertEqual(results, [0])
            self.assertEqual((folder / "nested/deep/note.txt").read_text(), "nested content")
            self.assertEqual((folder / "txt/root.txt").read_text(), "root content")
            self.assertNotIn("--recursive", controller.process.arguments())
            self.assertFalse(controller.running)

    def test_settings_and_rules_round_trip(self):
        first = Controller()
        first.folder = r"C:\media\日本語 é"
        first.landscapeFolder = "Wide media"
        first.setEnabled(0, False)
        first.moveRule(0, 1)
        second = Controller()
        self.assertEqual(second.folder, first.folder)
        self.assertEqual(second.landscapeFolder, "Wide media")
        self.assertEqual(second.rules, [{"id": "extension", "enabled": True}, {"id": "landscape", "enabled": False}]
                                 + [{"id": rule_id, "enabled": rule_id not in ("remove_empty_dirs", "flatten_videos", "flatten_images")} for rule_id in
                                    ("rename_images", "rename_videos", "photo_extensions", "video_extensions", "remove_empty_dirs", "landscape_images", "data_extensions", "music_videos", "flatten_videos", "flatten_images", "non_video_to_root", "non_image_to_root")])
        second.moveRule(5, -1)
        second.setEnabled(4, False)
        self.assertEqual(Controller().rules, second.rules)
        self.assertFalse(second.settings.fallbacksEnabled())

    def test_ui_edits_save_automatically_and_restore(self):
        controller = Controller()
        rule_ids = [rule["id"] for rule in controller.rules]
        qml = QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml"))
        engine = QQmlApplicationEngine()
        engine.addImageProvider("standard", StandardIconProvider())
        engine.setInitialProperties({"controller": controller})
        engine.load(qml)
        window = engine.rootObjects()[0]
        host = MainWindow(controller, window)
        host.show()
        host.activateWindow()
        self.assertTrue(QTest.qWaitForWindowActive(host))
        APP.processEvents()
        for name, value in (("inputFolder", r"C:\media\日本語 é"),):
            field = host.input_folder
            field.setFocus()
            QTest.keyClick(field, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            APP.sendEvent(field, QKeyEvent(QEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, value))
            APP.processEvents()
            self.assertEqual(field.property("text"), value)
        for name in [*[rule["id"] + "Enabled" for rule in controller.rules if rule["enabled"]], "extensionMoveUp"]:
            QTest.qWait(30)
            control = self.rule_control(window, name)
            position = control.mapToScene(QPointF(control.width() / 2, control.height() / 2)).toPoint()
            QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, position)
            APP.processEvents()
        host.close()
        restored = Controller()
        restored_engine = QQmlApplicationEngine()
        restored_engine.addImageProvider("standard", StandardIconProvider())
        restored_engine.setInitialProperties({"controller": restored})
        restored_engine.load(qml)
        restored_window = restored_engine.rootObjects()[0]
        restored_host = MainWindow(restored, restored_window)
        self.assertEqual(restored_host.input_folder.text(), r"C:\media\日本語 é")
        self.assertEqual(Path(restored.settings.fileName()), Path(restored.configFolder) / "FolderConformer.ini")
        for rule_id in rule_ids:
            self.assertFalse(self.rule_control(restored_window, rule_id + "Enabled").property("checked"))
        self.assertEqual(restored.rules, [{"id": rule_id, "enabled": False} for rule_id in
                                         [rule_ids[1], rule_ids[0], *rule_ids[2:]]])
        restored_host.close()

    def test_settings_dialog_saves_theme_and_moves_configuration(self):
        controller = Controller()
        controller.folder = str(Path(self.temporary.name) / "media")
        engine = QQmlApplicationEngine()
        engine.addImageProvider("standard", StandardIconProvider())
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
        self.assertIsNone(window.findChild(QObject, "ruleFoldersPanel"))
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
qt = app.QApplication([])
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
    host = next(widget for widget in qt.topLevelWidgets() if isinstance(widget, app.MainWindow))
    colors.append(host.folders_dock.palette().window().color().name())
    colors.append(host.folder_fields["videoFolder"].palette().base().color().name())
    colors.append(host.file_fields["videoExtensions"].palette().base().color().name())
    preview = host.preview.rootObject()
    for expression in ("palette.window.toString()", "palette.button.toString()", "palette.text.toString()"):
        colors.append(QQmlExpression(QQmlEngine.contextForObject(preview), preview, expression).evaluate()[0])
    colors.append(host.preview.grabFramebuffer().pixelColor(0, 0).name())
    window.close()
    return 0
with patch.object(app, "QApplication", return_value=qt), patch.object(app, "QQmlApplicationEngine", return_value=engine), patch.object(qt, "exec", side_effect=inspect), patch.object(sys, "argv", ["folderconformer"]):
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
                    palette.button().color().name(), palette.window().color().name(),
                    palette.window().color().name(), palette.base().color().name(), palette.base().color().name(),
                    palette.window().color().name(), palette.button().color().name(), palette.text().color().name(),
                    palette.window().color().name()])

    def test_qml_loads(self):
        controller = Controller()
        engine = QQmlApplicationEngine()
        engine.addImageProvider("standard", StandardIconProvider())
        messages = []
        engine.warnings.connect(lambda warnings: messages.extend(warning.toString() for warning in warnings))
        engine.setInitialProperties({"controller": controller})
        engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
        self.assertEqual(len(engine.rootObjects()), 1)
        window = engine.rootObjects()[0]
        APP.processEvents()
        self.assertIsNotNone(window.findChild(QQuickItem, "rulesPanel"))
        self.assertIsNone(window.findChild(QObject, "filesPanel"))
        for name in ("landscapeFolder", "videoFolder", "imageFolder"):
            self.assertIsNone(window.findChild(QObject, name))
        self.assertIsNone(window.findChild(QObject, "includeSubdirectories"))
        self.assertEqual(self.rule_control(window, "extensionEnabled").property("text"),
                         "Group loose files by extension")
        self.assertEqual(messages, [])
        window.close()

    def test_file_menu_selects_input_folder_and_quits(self):
        APP.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
        self.addCleanup(lambda: APP.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, False))
        controller = Controller()
        engine = QQmlApplicationEngine()
        engine.addImageProvider("standard", StandardIconProvider())
        messages = []
        engine.warnings.connect(lambda warnings: messages.extend(warning.toString() for warning in warnings))
        engine.setInitialProperties({"controller": controller})
        engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
        window = engine.rootObjects()[0]
        host = MainWindow(controller, window)
        host.show()
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
        self.assertFalse(window.property("choosingFolder"))
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
        self.assertFalse(window.property("choosingFolder"))
        self.assertEqual(Path(controller.folder), folder)
        self.assertEqual(host.input_folder.text(), controller.folder)
        self.assertEqual(Controller().folder, controller.folder)
        QMetaObject.invokeMethod(quit_menu, "triggered")
        APP.processEvents()
        self.assertFalse(host.isVisible())
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
                engine.addImageProvider("standard", StandardIconProvider())
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
