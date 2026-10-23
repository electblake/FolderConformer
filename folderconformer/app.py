import codecs
import json
import logging
import math
import os
import re
import sys
import subprocess
from pathlib import Path

import qt_themes
from platformdirs import user_config_path, user_log_path
from static_ffmpeg.run import get_platform_dir
from PySide6.QtCore import QElapsedTimer, QMetaObject, QObject, Property, QProcess, QProcessEnvironment, QRegularExpression, QSettings, Qt, QUrl, Signal, Slot, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon, QPalette, QRegularExpressionValidator, QStandardItem, QStandardItemModel
from PySide6.QtQml import QQmlApplicationEngine, QQmlEngine, QQmlProperty
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QCheckBox, QDockWidget, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QScrollArea, QStyle, QWidget

from folderconformer.updates import APP_NAME, APP_VERSION, Updates
from folderconformer.music_model import MODEL_VERSION, MUSIC_THRESHOLD


class StandardIconProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)
        self.icons = {
            "check": QStyle.StandardPixmap.SP_BrowserReload,
            "run": QStyle.StandardPixmap.SP_MediaPlay,
            "up": QStyle.StandardPixmap.SP_ArrowUp,
            "down": QStyle.StandardPixmap.SP_ArrowDown,
        }

    def requestPixmap(self, icon_id, size, requested_size):
        icon = QApplication.style().standardIcon(self.icons[icon_id])
        pixmap = icon.pixmap(requested_size, 1.0)
        size.setWidth(pixmap.width())
        size.setHeight(pixmap.height())
        return pixmap


class ActivityLogHandler(logging.Handler):
    def __init__(self, output):
        super().__init__()
        self.output = output
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    def emit(self, record):
        self.output.emit(self.format(record) + "\n")


class Controller(QObject):
    configurationChanged = Signal()
    checkStatusesChanged = Signal()
    runningChanged = Signal()
    runStateChanged = Signal()
    output = Signal(str)
    completed = Signal(int)
    progress = Signal(int, int, int)
    completionSummary = Signal(str)
    explorerCompleted = Signal(int)
    restartRequested = Signal()

    def __init__(self, folder=None):
        super().__init__()
        self.log_handler = ActivityLogHandler(self.output)
        logger = logging.getLogger("folderconformer")
        logger.setLevel(logging.INFO)
        logger.addHandler(self.log_handler)
        handler = self.log_handler
        self.destroyed.connect(lambda: logger.removeHandler(handler))
        self.restart_requested = False
        self._check_statuses = {}
        self._updates = Updates(self)
        self._run_state = ""
        self._kind = ""
        self._waiting = False
        settings_path = user_config_path("FolderConformer", appauthor=False) / "FolderConformer.ini"
        self.location_settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
        self.location_settings.setFallbacksEnabled(False)
        self._config_folder = self.location_settings.value("configFolder", str(settings_path.parent), type=str)
        self.settings = QSettings(str(Path(self._config_folder) / "FolderConformer.ini"), QSettings.Format.IniFormat)
        self.settings.setFallbacksEnabled(False)
        self._theme = self.settings.value("appearance/theme", "blender", type=str)
        self._folder = self.settings.value("folder", "", type=str)
        self._enumerate_conflicts = self.settings.value("enumerateConflicts", False, type=bool)
        self._landscape_folder = self.settings.value("landscapeFolder", "Landscape-FULL", type=str)
        self._music_video_folder = self.settings.value("musicVideoFolder", "with-music", type=str)
        self._music_threshold = self.settings.value("audio/musicThreshold", MUSIC_THRESHOLD, type=float)
        self._video_folder = self.settings.value("videoFolder", "video/", type=str)
        self._image_folder = self.settings.value("imageFolder", "photo/", type=str)
        self._data_folder = self.settings.value("dataFolder", "Data/", type=str)
        self._video_extensions = self.settings.value(
            "videoExtensions", "mp4;ts;m4v;wmv;avi;mov;mkv;webm;mpg;mpeg;mts;m2ts;m2v;vob;flv;3gp;3g2;ogv;asf", type=str
        )
        self._image_extensions = self.settings.value("imageExtensions", "jpg;jpeg;png;webp;heic", type=str)
        self._data_extensions = self.settings.value("dataExtensions", "csv;db;txt;", type=str)
        self._rules = json.loads(self.settings.value(
            "rules", json.dumps([{"id": rule_id, "enabled": True} for rule_id in (
                "landscape", "extension", "rename_images", "rename_videos", "photo_extensions", "video_extensions",
            )]), type=str
        ))
        if not any(rule["id"] == "remove_empty_dirs" for rule in self._rules):
            self._rules.append({"id": "remove_empty_dirs", "enabled": False})
        if not any(rule["id"] == "landscape_images" for rule in self._rules):
            self._rules.append({"id": "landscape_images", "enabled": True})
        if not any(rule["id"] == "data_extensions" for rule in self._rules):
            self._rules.append({"id": "data_extensions", "enabled": True})
        if not any(rule["id"] == "music_videos" for rule in self._rules):
            self._rules.append({"id": "music_videos", "enabled": True})
        for rule_id in ("flatten_videos", "flatten_images", "non_video_to_root", "non_image_to_root"):
            if not any(rule["id"] == rule_id for rule in self._rules):
                self._rules.append({"id": rule_id, "enabled": rule_id.startswith("non_")})
        self._target_tree = QStandardItemModel(self)
        self.configurationChanged.connect(self.update_target_tree)
        self.update_target_tree()
        if folder is not None:
            self.folder = folder
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONIOENCODING", "utf-8")
        self.process.setProcessEnvironment(environment)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.stateChanged.connect(self.runningChanged)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.process_error)

    @Property(QObject, constant=True)
    def targetTree(self):
        return self._target_tree

    def update_target_tree(self):
        enabled = {rule["id"] for rule in self._rules if rule["enabled"]}
        roots = []
        grouped_extensions = dict.fromkeys(
            value.strip().lstrip(".").lower()
            for configured in (self._image_extensions, self._video_extensions, self._data_extensions)
            for value in configured.split(";") if value.strip()
        )
        for key, name, configured, move_rule, rename_rule, landscape_rule in (
            ("images", self._image_folder, self._image_extensions, "photo_extensions", "rename_images", "landscape_images"),
            ("videos", self._video_folder, self._video_extensions, "video_extensions", "rename_videos", "landscape"),
            ("data", self._data_folder, self._data_extensions, "data_extensions", "", ""),
        ):
            children = []
            extensions = dict.fromkeys(value.strip().lstrip(".").lower()
                                       for value in configured.split(";") if value.strip())
            if landscape_rule in enabled:
                children.append(("landscape", self._landscape_folder,
                                 [(f"file.{extension}", f"file.{extension}", []) for extension in extensions]))
            if key == "videos" and "music_videos" in enabled:
                children.append(("music", self._music_video_folder,
                                 [(f"file.{extension}", f"file.{extension}", []) for extension in extensions]))
            flatten_rule = {"images": "flatten_images", "videos": "flatten_videos", "data": ""}[key]
            if move_rule in enabled or flatten_rule in enabled:
                for extension in extensions:
                    children.append((f"file.{extension}", f"file.{extension}", []))
                    if move_rule in enabled and extension in grouped_extensions:
                        del grouped_extensions[extension]
            if enabled.intersection((move_rule, rename_rule, landscape_rule, flatten_rule)) or (key == "videos" and "music_videos" in enabled):
                roots.append((key, name, children))
        if "extension" in enabled:
            for extension in grouped_extensions:
                roots.append((f"extension.{extension}", f"{extension}/",
                              [(f"file.{extension}", f"file.{extension}", [])]))
        self.sync_target_items(self._target_tree.invisibleRootItem(), roots)

    def sync_target_items(self, parent, entries):
        keys = {key for key, name, children in entries}
        for row in range(parent.rowCount() - 1, -1, -1):
            if parent.child(row).data(Qt.ItemDataRole.UserRole) not in keys:
                parent.removeRow(row)
        for row, (key, name, children) in enumerate(entries):
            if row == parent.rowCount() or parent.child(row).data(Qt.ItemDataRole.UserRole) != key:
                item = QStandardItem(name)
                item.setData(key, Qt.ItemDataRole.UserRole)
                item.setEditable(False)
                parent.insertRow(row, [item])
            item = parent.child(row)
            item.setText(name)
            self.sync_target_items(item, children)
        if parent.rowCount() > len(entries):
            parent.removeRows(len(entries), parent.rowCount() - len(entries))

    @Property(QObject, constant=True)
    def updates(self):
        return self._updates

    def save(self):
        self.settings.setValue("appearance/theme", self._theme)
        self.settings.setValue("folder", self._folder)
        self.settings.setValue("enumerateConflicts", self._enumerate_conflicts)
        self.settings.setValue("landscapeFolder", self._landscape_folder)
        self.settings.setValue("musicVideoFolder", self._music_video_folder)
        self.settings.setValue("audio/musicThreshold", self._music_threshold)
        self.settings.setValue("videoFolder", self._video_folder)
        self.settings.setValue("imageFolder", self._image_folder)
        self.settings.setValue("dataFolder", self._data_folder)
        self.settings.setValue("videoExtensions", self._video_extensions)
        self.settings.setValue("imageExtensions", self._image_extensions)
        self.settings.setValue("dataExtensions", self._data_extensions)
        self.settings.setValue("rules", json.dumps(self._rules))
        self.settings.sync()
        self.configurationChanged.emit()

    @Slot()
    def restart(self):
        self.save()
        self.location_settings.sync()
        self.restart_requested = True
        self.restartRequested.emit()
        QGuiApplication.quit()

    @Property("QStringList", constant=True)
    def themes(self):
        return ["", *sorted(qt_themes.get_themes())]

    @Property(str, notify=configurationChanged)
    def theme(self):
        return self._theme

    @theme.setter
    def theme(self, value):
        self._theme = value
        self.save()

    @Property(str, notify=configurationChanged)
    def folder(self):
        return self._folder

    @folder.setter
    def folder(self, value):
        self._folder = value
        self._check_statuses = {}
        self.checkStatusesChanged.emit()
        self.save()

    @Property(str, notify=configurationChanged)
    def landscapeFolder(self):
        return self._landscape_folder

    @landscapeFolder.setter
    def landscapeFolder(self, value):
        self._landscape_folder = value
        self._check_statuses = {}
        self.checkStatusesChanged.emit()
        self.save()

    @Property(bool, notify=configurationChanged)
    def enumerateConflicts(self):
        return self._enumerate_conflicts

    @enumerateConflicts.setter
    def enumerateConflicts(self, value):
        self._enumerate_conflicts = value
        self.save()

    @Property(str, notify=configurationChanged)
    def musicVideoFolder(self):
        return self._music_video_folder

    @musicVideoFolder.setter
    def musicVideoFolder(self, value):
        self._music_video_folder = value
        self._check_statuses = {}
        self.checkStatusesChanged.emit()
        self.save()

    @Property(float, notify=configurationChanged)
    def musicThreshold(self):
        return self._music_threshold

    @musicThreshold.setter
    def musicThreshold(self, value):
        self._music_threshold = value
        self._check_statuses = {}
        self.checkStatusesChanged.emit()
        self.save()

    @Property(str, notify=configurationChanged)
    def configFolder(self):
        return self._config_folder

    @configFolder.setter
    def configFolder(self, value):
        self.settings.sync()
        self._config_folder = value
        self.settings = QSettings(str(Path(value) / "FolderConformer.ini"), QSettings.Format.IniFormat)
        self.settings.setFallbacksEnabled(False)
        self.save()
        self.location_settings.setValue("configFolder", value)
        self.location_settings.sync()

    @Property(str, notify=configurationChanged)
    def videoFolder(self):
        return self._video_folder

    @videoFolder.setter
    def videoFolder(self, value):
        self._video_folder = value
        self._check_statuses = {}
        self.checkStatusesChanged.emit()
        self.save()

    @Property(str, notify=configurationChanged)
    def imageFolder(self):
        return self._image_folder

    @imageFolder.setter
    def imageFolder(self, value):
        self._image_folder = value
        self._check_statuses = {}
        self.checkStatusesChanged.emit()
        self.save()

    @Property(str, notify=configurationChanged)
    def dataFolder(self):
        return self._data_folder

    @dataFolder.setter
    def dataFolder(self, value):
        self._data_folder = value
        self._check_statuses = {}
        self.checkStatusesChanged.emit()
        self.save()

    @Property(str, notify=configurationChanged)
    def videoExtensions(self):
        return self._video_extensions

    @videoExtensions.setter
    def videoExtensions(self, value):
        self._video_extensions = value
        self._check_statuses = {}
        self.checkStatusesChanged.emit()
        self.save()

    @Property(str, notify=configurationChanged)
    def imageExtensions(self):
        return self._image_extensions

    @imageExtensions.setter
    def imageExtensions(self, value):
        self._image_extensions = value
        self._check_statuses = {}
        self.checkStatusesChanged.emit()
        self.save()

    @Property(str, notify=configurationChanged)
    def dataExtensions(self):
        return self._data_extensions

    @dataExtensions.setter
    def dataExtensions(self, value):
        self._data_extensions = value
        self._check_statuses = {}
        self.checkStatusesChanged.emit()
        self.save()

    @Property("QVariantList", notify=configurationChanged)
    def rules(self):
        return self._rules

    @Property("QVariantMap", notify=checkStatusesChanged)
    def checkStatuses(self):
        return self._check_statuses

    @Slot(str)
    def checkRule(self, rule_id):
        self._check_rule_id = rule_id
        self._check_statuses[rule_id] = "-"
        self.checkStatusesChanged.emit()
        self._run_state = ""
        self.runStateChanged.emit()
        self._launch("check", ["--check", self._folder, rule_id, self._video_folder, self._image_folder,
                               self._video_extensions, self._image_extensions, self._data_folder, self._data_extensions,
                               self._landscape_folder, self._music_video_folder, str(self._music_threshold)])

    @Slot()
    def checkAll(self):
        rule_ids = [rule["id"] for rule in self._rules if rule["enabled"]]
        for rule_id in rule_ids:
            self._check_statuses[rule_id] = "-"
        self.checkStatusesChanged.emit()
        self._run_state = ""
        self.runStateChanged.emit()
        self._launch("checks", ["--check-all", self._folder, json.dumps(rule_ids), self._video_folder,
                                self._image_folder, self._video_extensions, self._image_extensions,
                                self._data_folder, self._data_extensions, self._landscape_folder,
                                self._music_video_folder, str(self._music_threshold)])

    @Property(bool, notify=runningChanged)
    def checking(self):
        return self.running and self._kind in ("check", "checks")

    @Property(bool, notify=runningChanged)
    def running(self):
        return self.process.state() != QProcess.ProcessState.NotRunning

    @Property(str, notify=runStateChanged)
    def runState(self):
        return self._run_state

    @Slot()
    def pause(self):
        if self._run_state in ("pausing", "paused"):
            self._run_state = ""
            if self._waiting:
                self.process.write(b"continue\n")
                self._waiting = False
        else:
            self._run_state = "pausing"
        self.runStateChanged.emit()

    @Slot()
    def stop(self):
        self._run_state = "stopping"
        if self._waiting:
            self.process.write(b"stop\n")
            self._waiting = False
        self.runStateChanged.emit()

    @Slot()
    def cancel(self):
        self._run_state = "cancelling"
        self.runStateChanged.emit()
        self.process.kill()

    @Slot(QUrl)
    def selectFolder(self, url):
        self.folder = url.toLocalFile()

    @Slot(QUrl)
    def selectConfigFolder(self, url):
        self.configFolder = url.toLocalFile()

    @Slot()
    def openOutputFolder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self._folder).resolve())))

    @Slot()
    def openConfigFolder(self):
        path = Path(self._config_folder)
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    @Slot(int, bool)
    def setEnabled(self, index, enabled):
        self._rules[index]["enabled"] = enabled
        self._check_statuses = {key: value for key, value in self._check_statuses.items() if key != "music_videos"}
        self.checkStatusesChanged.emit()
        self.save()

    @Slot(int, int)
    def moveRule(self, index, offset):
        self._rules.insert(index + offset, self._rules.pop(index))
        self._check_statuses = {key: value for key, value in self._check_statuses.items() if key != "music_videos"}
        self.checkStatusesChanged.emit()
        self.save()

    @Slot()
    @Slot(int)
    def start(self, index=-1):
        self._run_state = ""
        self._waiting = False
        self._check_statuses = {}
        self.checkStatusesChanged.emit()
        self.runStateChanged.emit()
        rules = self._rules if index == -1 else [{"id": self._rules[index]["id"], "enabled": True}]
        arguments = ["--worker", self._folder, json.dumps(rules), self._landscape_folder,
                     self._video_folder, self._image_folder, self._video_extensions, self._image_extensions,
                     self._data_folder, self._data_extensions, self._music_video_folder,
                     str(self._music_threshold), "--controlled"]
        if self._enumerate_conflicts:
            arguments.append("--enumerate-conflicts")
        self._launch("conform", arguments)

    @Slot()
    def installExplorer(self):
        self._launch("explorer", ["--install-explorer"])

    def _launch(self, kind, arguments):
        self._kind = kind
        self.decoder = codecs.getincrementaldecoder("utf-8")()
        self.pending = ""
        self.timer = QElapsedTimer()
        self.timer.start()
        self.process.setProgram(str(Path(sys.executable).with_name("python.exe")))
        self.process.setArguments(["-I", "-u", "-X", "faulthandler", "-m", "folderconformer", *arguments])
        logging.getLogger(__name__).info("Starting %s: %s", kind,
                                         subprocess.list2cmdline([self.process.program(), *self.process.arguments()]))
        self.process.start()

    @Slot()
    def read_output(self):
        text = self.decoder.decode(bytes(self.process.readAllStandardOutput()))
        self.pending += text
        lines = self.pending.split("\n")
        self.pending = lines.pop()
        for line in lines:
            if self._kind in ("check", "checks") and line.startswith("Check: "):
                logging.getLogger("folderconformer.worker").info(line.rstrip("\r"))
                _, rule_id, status = line.split()
                self._check_statuses[rule_id] = status
                self.checkStatusesChanged.emit()
                continue
            if line.rstrip("\r") == "Control: ready":
                if self._run_state in ("pausing", "paused"):
                    self._waiting = True
                    self._run_state = "paused"
                    self.runStateChanged.emit()
                elif self._run_state == "stopping":
                    self.process.write(b"stop\n")
                elif self._run_state != "cancelling":
                    self.process.write(b"continue\n")
                continue
            logging.getLogger("folderconformer.worker").info(line.rstrip("\r"))
            if line.startswith("Completed: "):
                self.completionSummary.emit(line.removeprefix("Completed: ").rstrip("\r"))
            match = re.match(r"^\[(\d+)/(\d+)\] ", line)
            if match:
                current, total = map(int, match.groups())
                seconds = math.ceil((total - current) * self.timer.nsecsElapsed() / 1e9 / current)
                self.progress.emit(current, total, seconds)

    def process_error(self, error):
        self.read_output()
        logging.getLogger(__name__).error("%s process error %s: %s; command: %s", self._kind,
                                          error.name, self.process.errorString(),
                                          subprocess.list2cmdline([self.process.program(), *self.process.arguments()]))
        if self._kind == "check" and error == QProcess.ProcessError.FailedToStart:
            self._check_statuses[self._check_rule_id] = "ERR"
            self.checkStatusesChanged.emit()

    def finished(self, code, _status):
        self.read_output()
        tail = self.pending + self.decoder.decode(b"", final=True)
        if tail:
            logging.getLogger("folderconformer.worker").info(tail)
        self.pending = ""
        logging.getLogger(__name__).log(
            logging.ERROR if code != 0 or _status == QProcess.ExitStatus.CrashExit else logging.INFO,
            "%s process finished: exit_code=%s (0x%08X), exit_status=%s", self._kind, code,
            code & 0xFFFFFFFF, _status.name)
        if self._kind == "explorer":
            self.explorerCompleted.emit(code)
        elif self._kind in ("check", "checks"):
            if self._kind == "check" and (code != 0 or _status == QProcess.ExitStatus.CrashExit):
                self._check_statuses[self._check_rule_id] = "ERR"
                self.checkStatusesChanged.emit()
            self._run_state = ""
            self.runStateChanged.emit()
        else:
            self._waiting = False
            self._run_state = "cancelled" if self._run_state == "cancelling" else "stopped" if code == 2 else ""
            self.runStateChanged.emit()
            self.completed.emit(code)


class MainWindow(QMainWindow):
    def __init__(self, controller, quick_window):
        super().__init__()
        self.controller = controller
        self.quick_window = quick_window
        self.setWindowTitle(quick_window.title())
        quick_window.windowTitleChanged.connect(self.setWindowTitle)
        self.resize(1100, 720)
        container = QWidget.createWindowContainer(quick_window, self)
        container.setMinimumSize(640, quick_window.minimumHeight())
        quick_window.minimumHeightChanged.connect(container.setMinimumHeight)
        container.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCentralWidget(container)
        self.input_dock = QDockWidget(self.tr("Input folder"), self)
        self.input_dock.setObjectName("inputFolderDock")
        input_contents = QWidget()
        input_layout = QHBoxLayout(input_contents)
        self.input_folder = QLineEdit(controller.folder)
        self.input_folder.setObjectName("inputFolder")
        self.input_folder.setAccessibleName(self.tr("Input folder path"))
        self.input_folder.textEdited.connect(lambda text: setattr(controller, "folder", text))
        input_layout.addWidget(self.input_folder, 1)
        self.browse_input = QPushButton(self.tr("Browse…"))
        self.browse_input.setObjectName("browseInputFolder")
        self.browse_input.clicked.connect(lambda: quick_window.setProperty("choosingFolder", True))
        input_layout.addWidget(self.browse_input)
        self.input_dock.setWidget(input_contents)
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, self.input_dock)
        self.input_dock.visibilityChanged.connect(lambda visible: quick_window.setProperty("inputVisible", visible))
        quick_window.inputToggled.connect(self.input_dock.setVisible)
        controller.configurationChanged.connect(self.sync_input)
        self.preview_dock = QDockWidget(self.tr("Target folder preview"), self)
        self.preview_dock.setObjectName("targetTreeDock")
        self.preview = QQuickWidget(QQmlEngine.contextForObject(quick_window).engine(), self)
        self.preview.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.preview.setInitialProperties({"controller": controller, "font": quick_window.property("font")})
        self.preview.setSource(QUrl.fromLocalFile(str(Path(__file__).parent / "qml" / "TargetTree.qml")))
        preview_root = self.preview.rootObject()
        quick_window.fontChanged.connect(lambda: preview_root.setProperty("font", quick_window.property("font")))
        quick_window.paletteChanged.connect(self.sync_preview_palette)
        self.sync_preview_palette()
        self.preview.setMinimumSize(math.ceil(preview_root.implicitWidth()), math.ceil(preview_root.implicitHeight()))
        preview_root.implicitWidthChanged.connect(lambda: self.preview.setMinimumWidth(math.ceil(preview_root.implicitWidth())))
        preview_root.implicitHeightChanged.connect(lambda: self.preview.setMinimumHeight(math.ceil(preview_root.implicitHeight())))
        self.preview_dock.setWidget(self.preview)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.preview_dock)
        self.resizeDocks([self.preview_dock], [280], Qt.Orientation.Horizontal)
        self.preview_dock.visibilityChanged.connect(lambda visible: quick_window.setProperty("previewVisible", visible))
        quick_window.previewToggled.connect(self.preview_dock.setVisible)
        self.folders_dock = QDockWidget(self.tr("Folders"), self)
        self.folders_dock.setObjectName("foldersDock")
        contents = QWidget()
        form = QFormLayout(contents)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.folder_fields = {}
        for name, label in (("landscapeFolder", self.tr("Landscape folder name")),
                            ("musicVideoFolder", self.tr("Music Video folder")),
                            ("videoFolder", self.tr("Video folder")), ("imageFolder", self.tr("Image folder")),
                            ("dataFolder", self.tr("Data"))):
            field = QLineEdit(getattr(controller, name))
            field.setObjectName(name)
            field.setAccessibleName(label)
            field.textEdited.connect(lambda text, key=name: setattr(controller, key, text))
            form.addRow(label, field)
            self.folder_fields[name] = field
        self.folder_fields["landscapeFolder"].setValidator(QRegularExpressionValidator(
            QRegularExpression(r'[^<>:"/\\|?*.][^<>:"/\\|?*]*'), self))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(contents)
        self.folders_dock.setWidget(scroll)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.folders_dock)
        self.resizeDocks([self.folders_dock], [260], Qt.Orientation.Horizontal)
        self.folders_dock.visibilityChanged.connect(lambda visible: quick_window.setProperty("foldersVisible", visible))
        quick_window.foldersToggled.connect(self.folders_dock.setVisible)
        self.files_dock = QDockWidget(self.tr("Files"), self)
        self.files_dock.setObjectName("filesDock")
        files_contents = QWidget()
        files_form = QFormLayout(files_contents)
        files_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.file_fields = {}
        for name, text in (("videoExtensions", self.tr("Video file extensions (separated by semicolons)")),
                           ("imageExtensions", self.tr("Image file extensions (separated by semicolons)")),
                           ("dataExtensions", self.tr("Data file extensions (separated by semicolons)"))):
            field = QLineEdit(getattr(controller, name))
            field.setObjectName(name)
            field.setAccessibleName(text)
            field.textEdited.connect(lambda value, key=name: setattr(controller, key, value))
            label = QLabel(text)
            label.setWordWrap(True)
            label.setBuddy(field)
            files_form.addRow(label, field)
            self.file_fields[name] = field
        self.enumerate_conflicts = QCheckBox(self.tr("Resolve name conflicts (_1, _2, …)"))
        self.enumerate_conflicts.setObjectName("enumerateConflicts")
        self.enumerate_conflicts.setToolTip(self.tr("When unchecked, skip files whose destination name already exists."))
        self.enumerate_conflicts.setChecked(controller.enumerateConflicts)
        self.enumerate_conflicts.clicked.connect(lambda checked: setattr(controller, "enumerateConflicts", checked))
        files_form.addRow(self.enumerate_conflicts)
        files_scroll = QScrollArea()
        files_scroll.setWidgetResizable(True)
        files_scroll.setWidget(files_contents)
        self.files_dock.setWidget(files_scroll)
        self.splitDockWidget(self.folders_dock, self.files_dock, Qt.Orientation.Vertical)
        self.files_dock.visibilityChanged.connect(lambda visible: quick_window.setProperty("filesVisible", visible))
        quick_window.filesToggled.connect(self.files_dock.setVisible)
        self.audio_dock = QDockWidget(self.tr("Audio"), self)
        self.audio_dock.setObjectName("audioDock")
        audio_contents = QWidget()
        audio_form = QFormLayout(audio_contents)
        audio_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        audio_form.addRow(QLabel(self.tr("Music detection · %1").replace("%1", MODEL_VERSION)))
        self.music_threshold = QDoubleSpinBox()
        self.music_threshold.setObjectName("musicThreshold")
        self.music_threshold.setAccessibleName(self.tr("Music score threshold"))
        self.music_threshold.setRange(0.001, 1.0)
        self.music_threshold.setDecimals(3)
        self.music_threshold.setSingleStep(0.01)
        self.music_threshold.setValue(controller.musicThreshold)
        self.music_threshold.setToolTip(self.tr("Lower values detect music more readily. This score is not a probability of correctness."))
        self.music_threshold.valueChanged.connect(lambda value: setattr(controller, "musicThreshold", value))
        audio_form.addRow(self.tr("Music score threshold"), self.music_threshold)
        description = QLabel(self.tr("Detect music anywhere in each video, including under speech. All audio tracks and channels are analyzed locally."))
        description.setWordWrap(True)
        audio_form.addRow(description)
        audio_scroll = QScrollArea()
        audio_scroll.setWidgetResizable(True)
        audio_scroll.setWidget(audio_contents)
        self.audio_dock.setWidget(audio_scroll)
        self.splitDockWidget(self.files_dock, self.audio_dock, Qt.Orientation.Vertical)
        self.audio_dock.visibilityChanged.connect(lambda visible: quick_window.setProperty("audioVisible", visible))
        quick_window.audioToggled.connect(self.audio_dock.setVisible)
        controller.configurationChanged.connect(self.sync_audio)
        controller.configurationChanged.connect(self.sync_folders)
        controller.configurationChanged.connect(self.sync_files)
        controller.runningChanged.connect(self.sync_enabled)
        controller.updates.changed.connect(self.sync_enabled)
        quick_window.quitRequested.connect(self.close)
        controller.restartRequested.connect(self.close)
        self.sync_enabled()
        self.default_layout = self.saveState()
        quick_window.resetLayoutRequested.connect(lambda: self.restoreState(self.default_layout))
        if controller.settings.contains("window/geometry"):
            self.restoreGeometry(controller.settings.value("window/geometry"))
        if controller.settings.contains("window/state"):
            self.restoreState(controller.settings.value("window/state"))

    def sync_preview_palette(self):
        for group in ("active", "inactive", "disabled"):
            for role in ("window", "windowText", "base", "alternateBase", "text", "placeholderText",
                         "button", "buttonText", "brightText", "light", "midlight", "dark", "mid",
                         "shadow", "highlight", "highlightedText", "link", "linkVisited", "toolTipBase",
                         "toolTipText", "accent"):
                name = f"palette.{group}.{role}"
                QQmlProperty.write(self.preview.rootObject(), name, QQmlProperty.read(self.quick_window, name))

    def sync_input(self):
        if self.input_folder.text() != self.controller.folder:
            self.input_folder.setText(self.controller.folder)

    def sync_folders(self):
        for name, field in self.folder_fields.items():
            value = getattr(self.controller, name)
            if field.text() != value:
                field.setText(value)

    def sync_enabled(self):
        self.input_dock.widget().setEnabled(not self.controller.running and not self.controller.updates.busy)
        self.folders_dock.widget().setEnabled(not self.controller.running and not self.controller.updates.busy)
        self.files_dock.widget().setEnabled(not self.controller.running and not self.controller.updates.busy)
        self.audio_dock.widget().setEnabled(not self.controller.running and not self.controller.updates.busy)

    def sync_audio(self):
        self.music_threshold.setValue(self.controller.musicThreshold)

    def sync_files(self):
        self.enumerate_conflicts.setChecked(self.controller.enumerateConflicts)
        for name, field in self.file_fields.items():
            value = getattr(self.controller, name)
            if field.text() != value:
                field.setText(value)

    def closeEvent(self, event):
        if self.controller.running or self.controller.updates.busy:
            event.ignore()
            return
        self.controller.settings.setValue("window/geometry", self.saveGeometry())
        self.controller.settings.setValue("window/state", self.saveState())
        self.controller.settings.sync()
        QMetaObject.invokeMethod(self.quick_window, "closeDialogs")
        self.input_dock.close()
        self.preview_dock.close()
        self.folders_dock.close()
        self.files_dock.close()
        self.audio_dock.close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("FolderConformer")
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "FolderConformer.ico")))
    if len(sys.argv) > 1 and sys.argv[1] == "--install-explorer":
        sys.stdout.reconfigure(encoding="utf-8")
        from folderconformer.integrations import install
        return install()
    if len(sys.argv) > 1 and sys.argv[1] in ("--check", "--check-all"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        from folderconformer.pipeline import check_rule
        rule_ids = json.loads(sys.argv[3]) if sys.argv[1] == "--check-all" else [sys.argv[3]]
        for rule_id in rule_ids:
            status = check_rule(Path(sys.argv[2]), rule_id, sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7],
                                sys.argv[8], sys.argv[9], Path(get_platform_dir()) / "ffprobe.exe", sys.argv[10],
                                sys.argv[11], float(sys.argv[12]))
            print(f"Check: {rule_id} {status}", flush=True)
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        from folderconformer.pipeline import RunControl, conform
        tools = Path(get_platform_dir())
        control = RunControl() if "--controlled" in sys.argv[13:] else None
        conform(Path(sys.argv[2]), json.loads(sys.argv[3]), sys.argv[4], tools / "ffprobe.exe",
                sys.argv[5], sys.argv[6], sys.argv[7], sys.argv[8], sys.argv[9], sys.argv[10],
                control=control, enumerate_conflicts="--enumerate-conflicts" in sys.argv[13:],
                music_folder=sys.argv[11], music_threshold=float(sys.argv[12]))
        return 2 if control is not None and control.stopped else 0
    log_directory = user_log_path(APP_NAME, appauthor=False)
    log_directory.mkdir(parents=True, exist_ok=True)
    log_file = logging.FileHandler(log_directory / "FolderConformer.log", encoding="utf-8")
    log_file.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger = logging.getLogger("folderconformer")
    logger.addHandler(log_file)
    controller = Controller(sys.argv[1] if len(sys.argv) > 1 else None)

    def qt_message(message_type, context, message):
        level = {QtMsgType.QtDebugMsg: logging.DEBUG, QtMsgType.QtInfoMsg: logging.INFO,
                 QtMsgType.QtWarningMsg: logging.WARNING, QtMsgType.QtCriticalMsg: logging.ERROR,
                 QtMsgType.QtFatalMsg: logging.CRITICAL}[message_type]
        logging.getLogger("folderconformer.qt").log(level, "%s (%s:%s, %s)", message,
                                                   context.file, context.line, context.function)

    previous_qt_handler = qInstallMessageHandler(qt_message)
    if controller.theme:
        app.setStyle("Fusion")
        QQuickStyle.setStyle("Fusion")
        palette = QPalette()
        qt_themes.update_palette(palette, qt_themes.get_themes()[controller.theme])
        app.setPalette(palette)
    engine = QQmlApplicationEngine()
    engine.addImageProvider("standard", StandardIconProvider())
    engine.setInitialProperties({"controller": controller, "visible": False})
    engine.objectCreationFailed.connect(lambda: app.exit(1))
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent / "qml" / "Main.qml")))
    if controller.theme:
        window = engine.rootObjects()[0]
        for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
            for role in QPalette.ColorRole:
                if role in (QPalette.NoRole, QPalette.NColorRoles):
                    continue
                name = role.name[0].lower() + role.name[1:]
                QQmlProperty.write(window, f"palette.{group.name.lower()}.{name}", palette.color(group, role))
    host = MainWindow(controller, engine.rootObjects()[0])
    host.show()
    logger.info("%s %s started; log file: %s", APP_NAME, APP_VERSION, log_file.baseFilename)
    result = app.exec()
    qInstallMessageHandler(previous_qt_handler)
    logger.removeHandler(log_file)
    log_file.close()
    window = engine.rootObjects()[0]
    if window.property("pending_installer") is not None:
        os.startfile(window.property("pending_installer"))
    if controller.restart_requested:
        subprocess.Popen([sys.executable, "-I", "-m", "folderconformer"])
    return result
