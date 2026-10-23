import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import PropertyMock, patch

from PySide6.QtCore import Q_ARG, QEvent, QMetaObject, QObject, QPointF, Qt, QUrl
from PySide6.QtGui import QKeyEvent, QValidator
from PySide6.QtQml import QQmlApplicationEngine, QQmlProperty
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDockWidget, QLineEdit

from folderconformer.app import Controller, MainWindow, StandardIconProvider


APP = QApplication.instance() or QApplication([])


class DockingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.enterContext(patch("folderconformer.app.user_config_path", return_value=Path(temporary.name)))
        self.controller = Controller()
        self.engine = QQmlApplicationEngine()
        self.engine.addImageProvider("standard", StandardIconProvider())
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

    def test_input_dock_edits_browses_reopens_and_resets(self):
        dock = self.host.input_dock
        field = self.host.input_folder
        self.assertEqual(self.host.dockWidgetArea(dock), Qt.DockWidgetArea.TopDockWidgetArea)
        self.assertIsNone(self.quick.findChild(QObject, "inputFolder"))
        self.host.activateWindow()
        field.setFocus()
        value = r"C:\media\æ—¥æœ¬èªž Ã©"
        APP.sendEvent(field, QKeyEvent(QEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, value))
        self.assertEqual(self.controller.folder, value)
        self.assertEqual(Controller().folder, value)
        self.controller.folder = "C:/changed"
        self.assertEqual(field.text(), "C:/changed")
        field.setFocus()
        QTest.keyClick(field, Qt.Key.Key_Tab)
        self.assertTrue(self.host.browse_input.hasFocus())
        self.host.browse_input.click()
        APP.processEvents()
        self.assertTrue(self.quick.property("choosingFolder"))
        dialog = next(child for child in self.quick.findChildren(QObject)
                      if child.property("title") == "Select input folder")
        QMetaObject.invokeMethod(dialog, "reject")
        APP.processEvents()
        self.assertFalse(self.quick.property("choosingFolder"))
        dock.setFloating(True)
        self.assertTrue(dock.isFloating())
        dock.close()
        menu = self.quick.findChild(QObject, "inputFolderMenu")
        self.assertFalse(menu.property("checked"))
        QMetaObject.invokeMethod(menu, "triggered")
        self.assertTrue(dock.isVisible())
        self.assertTrue(menu.property("checked"))
        dock.setFloating(False)
        self.host.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.close()
        QMetaObject.invokeMethod(self.quick.findChild(QObject, "resetLayoutMenu"), "triggered")
        APP.processEvents()
        self.assertEqual(self.host.dockWidgetArea(dock), Qt.DockWidgetArea.TopDockWidgetArea)
        self.assertTrue(dock.isVisible())
        self.assertFalse(dock.isFloating())
        dock.setFloating(True)
        self.host.close()
        self.assertFalse(dock.isVisible())

    def test_preview_dock_moves_floats_reopens_and_resets(self):
        dock = self.host.preview_dock
        preview = self.host.preview.rootObject()
        tree = preview.findChild(QObject, "targetTree")
        self.assertEqual(self.host.dockWidgetArea(dock), Qt.DockWidgetArea.LeftDockWidgetArea)
        self.assertIsNone(self.quick.findChild(QObject, "targetTreePanel"))
        self.assertIs(tree.property("model"), self.controller.targetTree)
        QMetaObject.invokeMethod(preview.findChild(QObject, "openTargetTree"), "clicked")
        QTest.qWait(50)
        dock.setFloating(True)
        QTest.qWait(50)
        self.assertTrue(dock.isFloating())
        self.assertEqual(tree.property("rows"), 76)
        dock.close()
        menu = self.quick.findChild(QObject, "previewMenu")
        self.assertFalse(menu.property("checked"))
        self.assertTrue(self.host.input_dock.isVisible())
        QMetaObject.invokeMethod(menu, "triggered")
        self.assertTrue(dock.isVisible())
        self.assertTrue(menu.property("checked"))
        self.assertEqual(tree.property("rows"), 76)
        dock.setFloating(False)
        self.host.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.host.tabifyDockWidget(self.host.files_dock, dock)
        dock.close()
        QMetaObject.invokeMethod(self.quick.findChild(QObject, "resetLayoutMenu"), "triggered")
        APP.processEvents()
        self.assertEqual(self.host.dockWidgetArea(dock), Qt.DockWidgetArea.LeftDockWidgetArea)
        self.assertEqual(self.host.tabifiedDockWidgets(dock), [])
        self.assertTrue(dock.isVisible())
        self.assertFalse(dock.isFloating())
        self.controller.updates._busy = True
        self.controller.updates.changed.emit()
        self.assertFalse(preview.isEnabled())
        self.controller.updates._busy = False
        self.controller.updates.changed.emit()
        self.assertTrue(preview.isEnabled())
        dock.setFloating(True)
        self.host.close()
        self.assertFalse(dock.isVisible())

    def test_preview_font_palette_and_keyboard_controls(self):
        preview = self.host.preview.rootObject()
        tree = preview.findChild(QObject, "targetTree")
        font = self.host.font()
        font.setPointSize(18)
        self.host.setFont(font)
        self.quick.setProperty("font", font)
        QTest.qWait(50)
        self.assertEqual(preview.property("font").pointSize(), 18)
        self.assertEqual(QQmlProperty.read(preview, "palette.window"),
                         QQmlProperty.read(self.quick, "palette.window"))
        self.host.activateWindow()
        self.host.preview.setFocus()
        collapse = preview.findChild(QObject, "collapseTargetTree")
        expand = preview.findChild(QObject, "openTargetTree")
        collapse.forceActiveFocus()
        QTest.keyClick(self.host.preview, Qt.Key.Key_Tab)
        self.assertTrue(expand.hasActiveFocus())
        QTest.keyClick(self.host.preview, Qt.Key.Key_Space)
        QTest.qWait(50)
        self.assertEqual(tree.property("rows"), 76)
        QTest.keyClick(self.host.preview, Qt.Key.Key_Backtab)
        self.assertTrue(collapse.hasActiveFocus())
        QTest.keyClick(self.host.preview, Qt.Key.Key_Space)
        QTest.qWait(50)
        self.assertEqual(tree.property("rows"), 3)
        image = self.host.preview.grabFramebuffer()
        scale = image.width() / preview.width()
        for button in (collapse, expand):
            self.assertLessEqual(button.mapToScene(QPointF(button.width(), 0)).x(), preview.width())
            position = button.mapToScene(QPointF(5, button.height() / 2))
            background = image.pixelColor(int(position.x() * scale), int(position.y() * scale))
            text = button.property("contentItem").property("color")
            self.assertGreater(abs(text.lightnessF() - background.lightnessF()), 0.3)

    def test_audio_dock_settings_visibility_busy_and_reset(self):
        dock = self.host.audio_dock
        self.assertEqual(dock.objectName(), "audioDock")
        self.assertEqual(self.host.dockWidgetArea(dock), Qt.DockWidgetArea.RightDockWidgetArea)
        self.assertGreaterEqual(dock.y(), self.host.files_dock.y() + self.host.files_dock.height())
        self.host.music_threshold.setValue(0.75)
        self.host.folder_fields["musicVideoFolder"].textEdited.emit("Tunes")
        restored = Controller()
        self.assertEqual(restored.musicThreshold, 0.75)
        self.assertEqual(restored.musicVideoFolder, "Tunes")
        self.assertEqual(self.controller.targetTree.item(1).child(1).text(), "Tunes")
        self.controller.updates._busy = True
        self.controller.updates.changed.emit()
        self.assertFalse(self.host.music_threshold.isEnabled())
        self.controller.updates._busy = False
        self.controller.updates.changed.emit()
        dock.setFloating(True)
        dock.close()
        self.assertFalse(self.quick.property("audioVisible"))
        QMetaObject.invokeMethod(self.quick.findChild(QObject, "audioMenu"), "triggered")
        self.assertTrue(dock.isVisible())
        QMetaObject.invokeMethod(self.quick.findChild(QObject, "resetLayoutMenu"), "triggered")
        APP.processEvents()
        self.assertFalse(dock.isFloating())
        self.assertGreaterEqual(dock.y(), self.host.files_dock.y() + self.host.files_dock.height())
        dock.setFloating(True)
        self.host.close()
        self.assertFalse(dock.isVisible())

    def test_native_dock_moves_floats_closes_and_reopens(self):
        dock = self.host.folders_dock
        self.assertIsInstance(dock, QDockWidget)
        self.assertEqual(self.host.dockWidgetArea(dock), Qt.DockWidgetArea.RightDockWidgetArea)
        self.assertEqual(len(dock.findChildren(QLineEdit)), 5)
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

    def test_target_tree_shows_virtual_folders_and_updates_from_dock(self):
        tree = self.host.preview.rootObject().findChild(QObject, "targetTree")
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 3)
        QMetaObject.invokeMethod(self.host.preview.rootObject().findChild(QObject, "openTargetTree"), "clicked")
        QTest.qWait(50)
        model = self.controller.targetTree
        self.assertEqual(model.rowCount(), 3)
        self.assertEqual([model.item(row).text() for row in range(3)], ["photo/", "video/", "Data/"])
        self.assertEqual([model.item(row).rowCount() for row in range(3)], [6, 21, 3])
        self.assertEqual([model.item(2).child(row).text() for row in range(3)], ["file.csv", "file.db", "file.txt"])
        self.assertEqual([model.item(row).child(0).text() for row in (0, 1)], ["Landscape-FULL"] * 2)
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 76)
        preview = self.host.preview.rootObject()
        rules = self.quick.findChild(QObject, "rulesPanel")
        self.assertLessEqual(self.host.preview_dock.x() + self.host.preview_dock.width(),
                             self.host.centralWidget().x())
        QMetaObject.invokeMethod(tree, "collapse", Q_ARG(int, 0))
        self.host.activateWindow()
        for name, value in (("imageFolder", "Pictures/"), ("videoFolder", "Clips/"),
                            ("dataFolder", "Records/"), ("landscapeFolder", "Wide media")):
            field = self.host.folder_fields[name]
            field.setFocus()
            QTest.keyClick(field, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            QTest.keyClicks(field, value)
        APP.processEvents()
        self.assertIs(self.controller.targetTree, model)
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 65)
        self.assertEqual([model.item(row).text() for row in range(3)], ["Pictures/", "Clips/", "Records/"])
        self.assertEqual([model.item(row).child(0).text() for row in (0, 1)], ["Wide media"] * 2)
        QMetaObject.invokeMethod(tree, "expand", Q_ARG(int, 0))
        QTest.qWait(50)
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 76)
        restored_controller = Controller()
        restored = restored_controller.targetTree
        self.assertEqual([restored.item(row).text() for row in range(3)], ["Pictures/", "Clips/", "Records/"])
        self.assertFalse(model.item(0).isEditable())
        self.assertFalse(model.item(0).child(0).isEditable())

    def test_data_preview_tracks_extension_edits_and_empty_list(self):
        self.controller.imageExtensions = ""
        self.controller.videoExtensions = ""
        tree = self.host.preview.rootObject().findChild(QObject, "targetTree")
        QMetaObject.invokeMethod(self.host.preview.rootObject().findChild(QObject, "openTargetTree"), "clicked")
        QTest.qWait(50)
        data = self.controller.targetTree.item(2)
        field = self.host.file_fields["dataExtensions"]
        self.host.activateWindow()
        field.setFocus()
        QTest.keyClick(field, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(field, " .TXT;csv;TXT;json;xml; ;")
        QTest.qWait(50)
        self.assertEqual(data.rowCount(), 4)
        self.assertEqual([data.child(row).text() for row in range(4)],
                         ["file.txt", "file.csv", "file.json", "file.xml"])
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 10)
        self.assertGreaterEqual(tree.height(), tree.property("implicitHeight") - 1)
        self.assertFalse(data.child(0).isEditable())
        restored = Controller()
        self.assertEqual(restored.targetTree.item(2).child(3).text(), "file.xml")
        self.controller.dataExtensions = "csv"
        QTest.qWait(50)
        self.assertEqual(data.rowCount(), 1)
        self.assertEqual(data.child(0).text(), "file.csv")
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 7)
        self.controller.dataExtensions = ""
        QTest.qWait(50)
        self.assertEqual(data.rowCount(), 0)
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 6)

    def test_media_previews_track_extensions_in_roots_and_landscape_folders(self):
        tree = self.host.preview.rootObject().findChild(QObject, "targetTree")
        QMetaObject.invokeMethod(self.host.preview.rootObject().findChild(QObject, "openTargetTree"), "clicked")
        QTest.qWait(50)
        model = self.controller.targetTree
        self.host.activateWindow()
        for root_row, name, value, expected in (
            (0, "imageExtensions", " .PNG;jpg;PNG;webp; ;", ["file.png", "file.jpg", "file.webp"]),
            (1, "videoExtensions", " .MOV;mp4;MOV;mkv; ;", ["file.mov", "file.mp4", "file.mkv"]),
        ):
            with self.subTest(setting=name):
                media = model.item(root_row)
                landscape = media.child(0)
                field = self.host.file_fields[name]
                field.setFocus()
                QTest.keyClick(field, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
                QTest.keyClicks(field, value)
                QTest.qWait(50)
                self.assertEqual([media.child(row).text() for row in range(1 + root_row, media.rowCount())], expected)
                self.assertIs(media.child(0), landscape)
                self.assertEqual(landscape.text(), "Landscape-FULL")
                self.assertEqual([landscape.child(row).text() for row in range(landscape.rowCount())], expected)
                self.assertTrue(all(not landscape.child(row).isEditable() for row in range(landscape.rowCount())))
                self.assertTrue(all(not media.child(row).isEditable() for row in range(media.rowCount())))
                restored = Controller()
                self.assertEqual(restored.targetTree.item(root_row).child(3 + root_row).text(), expected[2])
                self.assertEqual(restored.targetTree.item(root_row).child(0).child(2).text(), expected[2])
                setattr(self.controller, name, "")
                self.assertEqual(media.rowCount(), 1 + root_row)
                self.assertIs(media.child(0), landscape)
                self.assertEqual(landscape.rowCount(), 0)
                setattr(self.controller, name, value)
        QMetaObject.invokeMethod(self.host.preview.rootObject().findChild(QObject, "openTargetTree"), "clicked")
        QTest.qWait(50)
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 24)
        self.assertEqual([model.item(2).child(row).text() for row in range(3)],
                         ["file.csv", "file.db", "file.txt"])

    def test_preview_follows_enabled_rule_destinations(self):
        self.controller.imageExtensions = "jpg"
        self.controller.videoExtensions = "mp4"
        self.controller.dataExtensions = "txt"
        tree = self.host.preview.rootObject().findChild(QObject, "targetTree")
        cases = (
            (set(), []),
            ({"remove_empty_dirs"}, []),
            ({"flatten_images"}, [("photo/", ["file.jpg"])]),
            ({"flatten_videos"}, [("video/", ["file.mp4"])]),
            ({"flatten_videos", "extension"}, [("video/", ["file.mp4"]), ("jpg/", ["file.jpg"]),
                                               ("mp4/", ["file.mp4"]), ("txt/", ["file.txt"])]),
            ({"rename_images"}, [("photo/", [])]),
            ({"rename_videos"}, [("video/", [])]),
            ({"landscape_images"}, [("photo/", ["Landscape-FULL"])]),
            ({"landscape"}, [("video/", ["Landscape-FULL"])]),
            ({"photo_extensions"}, [("photo/", ["file.jpg"])]),
            ({"video_extensions"}, [("video/", ["file.mp4"])]),
            ({"data_extensions"}, [("Data/", ["file.txt"])]),
            ({"extension"}, [("jpg/", ["file.jpg"]), ("mp4/", ["file.mp4"]), ("txt/", ["file.txt"])]),
            ({"extension", "photo_extensions", "landscape_images", "data_extensions"},
             [("photo/", ["Landscape-FULL", "file.jpg"]), ("Data/", ["file.txt"]), ("mp4/", ["file.mp4"])]),
            ({"photo_extensions", "video_extensions", "data_extensions", "landscape", "landscape_images"},
             [("photo/", ["Landscape-FULL", "file.jpg"]), ("video/", ["Landscape-FULL", "file.mp4"]),
              ("Data/", ["file.txt"])]),
        )
        for enabled, expected in cases:
            with self.subTest(enabled=enabled):
                for index, rule in enumerate(self.controller.rules):
                    self.controller.setEnabled(index, rule["id"] in enabled)
                QMetaObject.invokeMethod(self.host.preview.rootObject().findChild(QObject, "openTargetTree"), "clicked")
                QTest.qWait(50)
                model = self.controller.targetTree
                actual = [(model.item(row).text(), [model.item(row).child(child).text()
                           for child in range(model.item(row).rowCount())]) for row in range(model.rowCount())]
                self.assertEqual(actual, expected)
                QMetaObject.invokeMethod(tree, "forceLayout")
                self.assertEqual(tree.property("rows"), sum(1 + len(children) for name, children in expected)
                                 + len(enabled.intersection({"landscape", "landscape_images"})))
                for row in range(model.rowCount()):
                    for child in range(model.item(row).rowCount()):
                        item = model.item(row).child(child)
                        if item.text() == "Landscape-FULL":
                            self.assertEqual(item.rowCount(), 1)
                            self.assertEqual(item.child(0).text(), "file.jpg" if model.item(row).text() == "photo/" else "file.mp4")
                        else:
                            self.assertEqual(item.rowCount(), 0)
        restored = Controller()
        self.assertEqual(restored.targetTree.rowCount(), 3)
        self.controller.moveRule(0, 1)
        self.assertEqual(self.controller.targetTree.rowCount(), 3)

    def test_preview_scrolls_independently_and_defaults_collapsed(self):
        tree = self.host.preview.rootObject().findChild(QObject, "targetTree")
        preview = self.host.preview.rootObject()
        rules = self.quick.findChild(QObject, "rulesPanel")
        rules_scroll = self.quick.findChild(QObject, "settingsScroll").property("contentItem")
        open_all = self.host.preview.rootObject().findChild(QObject, "openTargetTree")
        collapse_all = self.host.preview.rootObject().findChild(QObject, "collapseTargetTree")
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 3)
        preview_height = preview.height()
        rules_y = rules.mapToScene(QPointF(0, 0)).y()
        self.assertLess(rules_y, self.quick.height())
        self.assertGreater(open_all.mapToScene(QPointF(0, 0)).x(), preview.width() / 2)
        self.assertLessEqual(open_all.mapToScene(QPointF(0, open_all.height())).y(),
                             tree.mapToScene(QPointF(0, 0)).y())
        QMetaObject.invokeMethod(open_all, "clicked")
        QTest.qWait(50)
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 76)
        self.assertGreater(tree.property("contentHeight"), tree.height())
        self.assertTrue(self.host.preview.rootObject().findChild(QObject, "targetTreeScrollBar").property("visible"))
        tree.setProperty("contentY", 120)
        QTest.qWait(50)
        self.assertGreater(tree.property("contentY"), 0)
        self.assertEqual(rules_scroll.property("contentY"), 0)
        self.assertEqual(preview.height(), preview_height)
        self.assertEqual(rules.mapToScene(QPointF(0, 0)).y(), rules_y)
        QMetaObject.invokeMethod(collapse_all, "clicked")
        QTest.qWait(50)
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 3)
        self.controller.setEnabled(0, False)
        self.controller.imageExtensions = "png;jpg"
        QTest.qWait(50)
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 3)
        self.assertEqual(preview.height(), preview_height)

    def test_landscape_preview_children_start_collapsed(self):
        tree = self.host.preview.rootObject().findChild(QObject, "targetTree")
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 3)
        QMetaObject.invokeMethod(tree, "expand", Q_ARG(int, 0))
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 9)
        QMetaObject.invokeMethod(tree, "expand", Q_ARG(int, 1))
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 14)
        QMetaObject.invokeMethod(self.host.preview.rootObject().findChild(QObject, "collapseTargetTree"), "clicked")
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 3)
        QMetaObject.invokeMethod(tree, "expand", Q_ARG(int, 0))
        QMetaObject.invokeMethod(tree, "forceLayout")
        self.assertEqual(tree.property("rows"), 9)

    def test_folder_edits_persist_update_rules_and_keep_keyboard_order(self):
        values = {"landscapeFolder": "Wide media Ã©", "videoFolder": "Clips/", "imageFolder": "Pictures/", "dataFolder": "Records/"}
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
        self.assertEqual(self.host.folder_fields["videoFolder"].text(), "Updated/")
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
        fields = [self.host.input_folder, self.host.browse_input, *self.host.folder_fields.values(), *self.host.file_fields.values(), self.host.enumerate_conflicts]
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
        for field in [self.host.input_folder, *self.host.folder_fields.values(), *self.host.file_fields.values()]:
            self.assertGreaterEqual(field.height(), field.sizeHint().height())
            self.assertGreaterEqual(field.width(), field.minimumSizeHint().width())
        scroll = self.host.folders_dock.widget()
        self.assertTrue(scroll.widgetResizable())
        self.assertGreaterEqual(self.quick.width(), 640)
        tree = self.host.preview.rootObject().findChild(QObject, "targetTree")
        preview = self.host.preview.rootObject()
        rules = self.quick.findChild(QObject, "rulesPanel")
        self.assertGreaterEqual(tree.height(), tree.property("implicitHeight") - 1)
        self.assertLessEqual(self.host.preview_dock.x() + self.host.preview_dock.width(),
                             self.host.centralWidget().x())
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
        self.assertGreaterEqual(scroll.property("contentWidth"), scroll.property("availableWidth"))
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
engine.addImageProvider("standard", app.StandardIconProvider())
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
            for index, dock in enumerate((host.folders_dock, host.files_dock, host.input_dock, host.preview_dock, host.audio_dock)):
                dock.setFloating(True)
                dock.setGeometry(160 + index * 400, 180, 350, 420)
            if sys.argv[3] == "folders_closed":
                host.folders_dock.close()
            if sys.argv[3] == "preview_closed":
                host.preview_dock.close()
            if sys.argv[3] == "input_closed":
                host.input_dock.close()
            if sys.argv[3] == "audio_closed":
                host.audio_dock.close()
            if sys.argv[3] == "files_closed":
                host.files_dock.close()
    QTest.qWait(100)
    result["window"] = host.geometry().getRect()
    result["docks"] = [
        [dock.objectName(), host.dockWidgetArea(dock).value, dock.isFloating(),
         dock.isVisible(), dock.geometry().getRect(),
         quick.findChild(QObject, menu).property("checked")]
        for dock, menu in ((host.folders_dock, "foldersMenu"), (host.files_dock, "filesMenu"), (host.input_dock, "inputFolderMenu"), (host.preview_dock, "previewMenu"), (host.audio_dock, "audioMenu"))
    ]
    if sys.argv[4] == "restart":
        controller.restart()
    else:
        host.close()
QTimer.singleShot(100, inspect)
qt.exec()
print(json.dumps(result))
"""
        for scenario in ("docked", "floating", "folders_closed", "files_closed", "input_closed", "preview_closed", "audio_closed"):
            for shutdown in ("close", "restart"):
                with self.subTest(scenario=scenario, shutdown=shutdown):
                    with tempfile.TemporaryDirectory() as directory:
                        saved = subprocess.run(
                            [sys.executable, "-c", script, directory, "save", scenario, shutdown],
                            capture_output=True, text=True, timeout=15)
                        self.assertEqual(saved.returncode, 0, saved.stderr)
                        restored = subprocess.run(
                            [sys.executable, "-c", script, directory, "restore", scenario, "close"],
                            capture_output=True, text=True, timeout=15)
                        self.assertEqual(restored.returncode, 0, restored.stderr)
                        self.assertEqual(json.loads(restored.stdout), json.loads(saved.stdout))
