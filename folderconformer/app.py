import codecs
import json
import math
import os
import re
import sys
from pathlib import Path

from platformdirs import user_config_path
from static_ffmpeg.run import get_platform_dir
from PySide6.QtCore import QElapsedTimer, QObject, Property, QProcess, QProcessEnvironment, QSettings, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine

from folderconformer.updates import APP_NAME, APP_VERSION, Updates


class Controller(QObject):
    configurationChanged = Signal()
    runningChanged = Signal()
    runStateChanged = Signal()
    output = Signal(str)
    completed = Signal(int)
    progress = Signal(int, int, int)
    completionSummary = Signal(str)
    explorerCompleted = Signal(int)

    def __init__(self, folder=None):
        super().__init__()
        self._updates = Updates(self)
        self._run_state = ""
        self._waiting = False
        settings_path = user_config_path("FolderConformer", appauthor=False) / "FolderConformer.ini"
        self.location_settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
        self.location_settings.setFallbacksEnabled(False)
        self._config_folder = self.location_settings.value("configFolder", str(settings_path.parent), type=str)
        self.settings = QSettings(str(Path(self._config_folder) / "FolderConformer.ini"), QSettings.Format.IniFormat)
        self.settings.setFallbacksEnabled(False)
        self._folder = self.settings.value("folder", "", type=str)
        self._include_subdirectories = self.settings.value("includeSubdirectories", False, type=bool)
        self._landscape_folder = self.settings.value("landscapeFolder", "Landscape-FULL", type=str)
        self._video_folder = self.settings.value("videoFolder", "video/", type=str)
        self._image_folder = self.settings.value("imageFolder", "photo/", type=str)
        self._video_extensions = self.settings.value(
            "videoExtensions", "mp4;ts;m4v;wmv;avi;mov;mkv;webm;mpg;mpeg;mts;m2ts;m2v;vob;flv;3gp;3g2;ogv;asf", type=str
        )
        self._image_extensions = self.settings.value("imageExtensions", "jpg;jpeg;png;webp;heic", type=str)
        self._rules = json.loads(self.settings.value(
            "rules", json.dumps([{"id": rule_id, "enabled": True} for rule_id in (
                "landscape", "extension", "rename_images", "rename_videos", "photo_extensions", "video_extensions",
            )]), type=str
        ))
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
        self.process.errorOccurred.connect(lambda _: self.output.emit(self.process.errorString()))

    @Property(QObject, constant=True)
    def updates(self):
        return self._updates

    def save(self):
        self.settings.setValue("folder", self._folder)
        self.settings.setValue("includeSubdirectories", self._include_subdirectories)
        self.settings.setValue("landscapeFolder", self._landscape_folder)
        self.settings.setValue("videoFolder", self._video_folder)
        self.settings.setValue("imageFolder", self._image_folder)
        self.settings.setValue("videoExtensions", self._video_extensions)
        self.settings.setValue("imageExtensions", self._image_extensions)
        self.settings.setValue("rules", json.dumps(self._rules))
        self.settings.sync()
        self.configurationChanged.emit()

    @Property(str, notify=configurationChanged)
    def folder(self):
        return self._folder

    @folder.setter
    def folder(self, value):
        self._folder = value
        self.save()

    @Property(str, notify=configurationChanged)
    def landscapeFolder(self):
        return self._landscape_folder

    @landscapeFolder.setter
    def landscapeFolder(self, value):
        self._landscape_folder = value
        self.save()

    @Property(bool, notify=configurationChanged)
    def includeSubdirectories(self):
        return self._include_subdirectories

    @includeSubdirectories.setter
    def includeSubdirectories(self, value):
        self._include_subdirectories = value
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
        self.save()

    @Property(str, notify=configurationChanged)
    def imageFolder(self):
        return self._image_folder

    @imageFolder.setter
    def imageFolder(self, value):
        self._image_folder = value
        self.save()

    @Property(str, notify=configurationChanged)
    def videoExtensions(self):
        return self._video_extensions

    @videoExtensions.setter
    def videoExtensions(self, value):
        self._video_extensions = value
        self.save()

    @Property(str, notify=configurationChanged)
    def imageExtensions(self):
        return self._image_extensions

    @imageExtensions.setter
    def imageExtensions(self, value):
        self._image_extensions = value
        self.save()

    @Property("QVariantList", notify=configurationChanged)
    def rules(self):
        return self._rules

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
    def openConfigFolder(self):
        path = Path(self._config_folder)
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    @Slot(int, bool)
    def setEnabled(self, index, enabled):
        self._rules[index]["enabled"] = enabled
        self.save()

    @Slot(int, int)
    def moveRule(self, index, offset):
        self._rules.insert(index + offset, self._rules.pop(index))
        self.save()

    @Slot()
    def start(self):
        self._run_state = ""
        self._waiting = False
        self.runStateChanged.emit()
        arguments = ["--worker", self._folder, json.dumps(self._rules), self._landscape_folder,
                     self._video_folder, self._image_folder, self._video_extensions, self._image_extensions,
                     "--controlled"]
        if self._include_subdirectories:
            arguments.append("--recursive")
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
        self.process.setArguments(["-I", "-m", "folderconformer", *arguments])
        self.process.start()

    @Slot()
    def read_output(self):
        text = self.decoder.decode(bytes(self.process.readAllStandardOutput()))
        self.pending += text
        lines = self.pending.split("\n")
        self.pending = lines.pop()
        for line in lines:
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
            self.output.emit(line + "\n")
            if line.startswith("Completed: "):
                self.completionSummary.emit(line.removeprefix("Completed: ").rstrip("\r"))
            match = re.match(r"^\[(\d+)/(\d+)\] ", line)
            if match:
                current, total = map(int, match.groups())
                seconds = math.ceil((total - current) * self.timer.nsecsElapsed() / 1e9 / current)
                self.progress.emit(current, total, seconds)

    def finished(self, code, _status):
        self.read_output()
        self.output.emit(self.pending + self.decoder.decode(b"", final=True))
        if self._kind == "explorer":
            self.explorerCompleted.emit(code)
        else:
            self._waiting = False
            self._run_state = "cancelled" if self._run_state == "cancelling" else "stopped" if code == 2 else ""
            self.runStateChanged.emit()
            self.completed.emit(code)


def main():
    app = QGuiApplication(sys.argv)
    app.setOrganizationName("FolderConformer")
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "FolderConformer.ico")))
    if len(sys.argv) > 1 and sys.argv[1] == "--install-explorer":
        sys.stdout.reconfigure(encoding="utf-8")
        from folderconformer.integrations import install
        return install()
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        from folderconformer.pipeline import RunControl, conform
        tools = Path(get_platform_dir())
        control = RunControl() if "--controlled" in sys.argv[9:] else None
        conform(Path(sys.argv[2]), json.loads(sys.argv[3]), sys.argv[4], tools / "ffprobe.exe",
                sys.argv[5], sys.argv[6], sys.argv[7], sys.argv[8], recursive="--recursive" in sys.argv[9:],
                control=control)
        return 2 if control is not None and control.stopped else 0
    controller = Controller(sys.argv[1] if len(sys.argv) > 1 else None)
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"controller": controller})
    engine.objectCreationFailed.connect(lambda: app.exit(1))
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent / "qml" / "Main.qml")))
    result = app.exec()
    window = engine.rootObjects()[0]
    if window.property("pending_installer") is not None:
        os.startfile(window.property("pending_installer"))
    return result
