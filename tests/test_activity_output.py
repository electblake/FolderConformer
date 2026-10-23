import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QMetaObject, QObject, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from folderconformer.app import ActivityLogHandler, Controller, StandardIconProvider


APP = QApplication.instance() or QApplication([])


class ActivityOutputTests(unittest.TestCase):
    def test_pending_log_is_bounded_for_one_hundred_thousand_messages(self):
        handler = ActivityLogHandler()
        record = logging.LogRecord("folderconformer.worker", logging.INFO, "", 0, "[H2] " + "x" * 150, (), None)
        for _ in range(100000):
            handler.handle(record)
        self.assertLessEqual(len(handler.lines), 1000)
        self.assertLessEqual(handler.characters, 100000)
        text = handler.drain()
        self.assertLessEqual(len(text), 100000)
        self.assertEqual(handler.characters, 0)
        self.assertEqual(handler.drain(), "")

    def test_display_is_bounded_clear_clears_pending_and_bottom_scrolls(self):
        with tempfile.TemporaryDirectory() as temporary, patch("folderconformer.app.user_config_path", return_value=Path(temporary)):
            controller = Controller()
            engine = QQmlApplicationEngine()
            engine.addImageProvider("standard", StandardIconProvider())
            engine.setInitialProperties({"controller": controller})
            engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / "folderconformer/qml/Main.qml")))
            window = engine.rootObjects()[0]
            log = window.findChild(QObject, "applicationLog")
            controller.output.emit("".join(f"[H2] item {i}\n" for i in range(100000)))
            self.assertLessEqual(len(log.property("text")), 100000)
            self.assertLessEqual(len(log.property("text").splitlines()), 1000)
            self.assertIn("item 99999", log.property("text"))
            self.assertNotIn("item 0\n", log.property("text"))
            QTest.qWait(50)
            scroll = window.findChild(QObject, "outputScroll").property("contentItem")
            scroll.setProperty("contentY", 0)
            QMetaObject.invokeMethod(window.findChild(QObject, "goToBottom"), "clicked")
            APP.processEvents()
            self.assertAlmostEqual(scroll.property("contentY"), scroll.property("contentHeight") - scroll.property("height"), delta=2)
            record = logging.LogRecord("folderconformer.worker", logging.INFO, "", 0, "[N4] pending", (), None)
            controller.log_handler.handle(record)
            QMetaObject.invokeMethod(window.findChild(QObject, "clearOutput"), "clicked")
            controller.flush_output()
            self.assertEqual(log.property("text"), "")
            controller.output.emit("previous execution\n")
            controller.folder = temporary
            controller._rules = [{"id": "create_empty_file", "enabled": True}]
            controller.start()
            self.assertNotIn("previous execution", log.property("text"))
            self.assertTrue(controller.process.waitForFinished(10000))
            self.assertEqual(controller.process.exitCode(), 0)
            self.assertIn("[E1]", log.property("text"))
            window.close()

    def test_controller_batches_log_delivery(self):
        with tempfile.TemporaryDirectory() as temporary, patch("folderconformer.app.user_config_path", return_value=Path(temporary)):
            controller = Controller()
            output = []
            controller.output.connect(output.append)
            record = logging.LogRecord("folderconformer.worker", logging.INFO, "", 0, "[M5] Audio", (), None)
            for _ in range(5000):
                controller.log_handler.handle(record)
            self.assertEqual(output, [])
            controller.flush_output()
            self.assertEqual(len(output), 1)
            self.assertLessEqual(len(output[0]), 100000)
