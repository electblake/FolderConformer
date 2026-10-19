import codecs
import json
import math
import re
import sys
import tomllib
from pathlib import Path

from platformdirs import user_config_path
from PySide6.QtCore import QElapsedTimer, QObject, Property, QProcess, QProcessEnvironment, QSettings, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine


class Controller(QObject):
    configurationChanged = Signal()
    runningChanged = Signal()
    output = Signal(str)
    completed = Signal(int)
    progress = Signal(int, int, int)
    completionSummary = Signal(str)

    def __init__(self):
        super().__init__()
        settings_path = user_config_path("FolderConformer", appauthor=False) / "FolderConformer.ini"
        self.settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
        self.settings.setFallbacksEnabled(False)
        self._folder = self.settings.value("folder", "", type=str)
        self._include_subdirectories = self.settings.value("includeSubdirectories", False, type=bool)
        self._landscape_folder = self.settings.value("landscapeFolder", "Landscape-FULL", type=str)
        self._rules = json.loads(self.settings.value(
            "rules", json.dumps([{"id": rule_id, "enabled": True} for rule_id in (
                "landscape", "extension", "rename_images", "rename_videos", "photo_extensions", "video_extensions",
            )]), type=str
        ))
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONIOENCODING", "utf-8")
        self.process.setProcessEnvironment(environment)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.stateChanged.connect(self.runningChanged)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(lambda _: self.output.emit(self.process.errorString()))

    def save(self):
        self.settings.setValue("folder", self._folder)
        self.settings.setValue("includeSubdirectories", self._include_subdirectories)
        self.settings.setValue("landscapeFolder", self._landscape_folder)
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

    @Property("QVariantList", notify=configurationChanged)
    def rules(self):
        return self._rules

    @Property(bool, notify=runningChanged)
    def running(self):
        return self.process.state() != QProcess.ProcessState.NotRunning

    @Slot(QUrl)
    def selectFolder(self, url):
        self.folder = url.toLocalFile()

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
        self.decoder = codecs.getincrementaldecoder("utf-8")()
        self.pending = ""
        self.timer = QElapsedTimer()
        self.timer.start()
        arguments = ["--worker", self._folder, json.dumps(self._rules), self._landscape_folder]
        if self._include_subdirectories:
            arguments.append("--recursive")
        if getattr(sys, "frozen", False):
            self.process.setProgram(sys.executable)
        else:
            self.process.setProgram(sys.executable)
            arguments = [str(Path(__file__).parent.parent / "main.py"), *arguments]
        self.process.setArguments(arguments)
        self.process.start()

    @Slot()
    def read_output(self):
        text = self.decoder.decode(bytes(self.process.readAllStandardOutput()))
        self.output.emit(text)
        self.pending += text
        lines = self.pending.split("\n")
        self.pending = lines.pop()
        for line in lines:
            if line.startswith("Completed: "):
                self.completionSummary.emit(line.removeprefix("Completed: ").rstrip("\r"))
            match = re.match(r"^\[(\d+)/(\d+)\] ", line)
            if match:
                current, total = map(int, match.groups())
                seconds = math.ceil((total - current) * self.timer.nsecsElapsed() / 1e9 / current)
                self.progress.emit(current, total, seconds)

    def finished(self, code, _status):
        self.read_output()
        self.output.emit(self.decoder.decode(b"", final=True))
        self.completed.emit(code)


def main():
    app = QGuiApplication(sys.argv)
    app.setOrganizationName("FolderConformer")
    app.setApplicationName("FolderConformer")
    base = Path(__file__).resolve().parent.parent
    metadata = tomllib.loads((base / "pyproject.toml").read_text(encoding="utf-8"))
    app.setApplicationVersion(metadata["project"]["version"])
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        from folderconformer.pipeline import conform
        tools = base / ("tools" if getattr(sys, "frozen", False) else "build/tools")
        conform(Path(sys.argv[2]), json.loads(sys.argv[3]), sys.argv[4], tools / "ffprobe.exe",
                recursive="--recursive" in sys.argv[5:])
        return 0
    controller = Controller()
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"controller": controller})
    engine.objectCreationFailed.connect(lambda: app.exit(1))
    engine.load(QUrl.fromLocalFile(str(base / "folderconformer" / "qml" / "Main.qml")))
    return app.exec()
