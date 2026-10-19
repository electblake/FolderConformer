import json
import platform
from importlib.metadata import version
from urllib.request import Request, urlopen

from platformdirs import user_cache_path
from PySide6.QtCore import QObject, Property, QThread, Signal, Slot


APP_NAME = "FolderConformer"
APP_VERSION = version("folderconformer")
GITHUB_REPOSITORY = "electblake/folderconformer"
GITHUB_API_VERSION = "2022-11-28"
RELEASES_URL = f"https://github.com/{GITHUB_REPOSITORY}/releases"


def version_tuple(value):
    return tuple(int(part) for part in value.split("."))


class UpdateWorker(QThread):
    releaseFetched = Signal(str, bool, object)
    downloadProgress = Signal(object, object)
    downloaded = Signal(str)

    def __init__(self, asset=None, parent=None):
        super().__init__(parent)
        self.asset = asset

    def run(self):
        if self.asset is None:
            request = Request(
                f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest",
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": f"{APP_NAME}/{APP_VERSION}",
                    "X-GitHub-Api-Version": GITHUB_API_VERSION,
                },
            )
            with urlopen(request, timeout=30) as response:
                release = json.load(response)
            latest = release["tag_name"].removeprefix("v")
            available = version_tuple(latest) > version_tuple(APP_VERSION)
            asset = None
            if available:
                name = (
                    f"{APP_NAME}-{latest}-{platform.system().lower()}-"
                    f"{platform.machine().lower()}-Setup.exe"
                )
                asset = next(a for a in release["assets"] if a["name"] == name)
            self.releaseFetched.emit(latest, available, asset)
        else:
            directory = user_cache_path(APP_NAME, appauthor=False) / "updates"
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / self.asset["name"]
            current = 0
            with urlopen(self.asset["browser_download_url"], timeout=30) as response, path.open("wb") as installer:
                while chunk := response.read(256 * 1024):
                    installer.write(chunk)
                    current += len(chunk)
                    self.downloadProgress.emit(current, self.asset["size"])
            self.downloaded.emit(str(path))


class Updates(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False
        self._available = False
        self._installer_path = ""
        self._status = ""
        self._versions = f"Installed: {APP_VERSION}"
        self._progress = 0
        self._indeterminate = False
        self.asset = None
        self.workers = []

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(bool, notify=changed)
    def available(self):
        return self._available

    @Property(bool, notify=changed)
    def ready(self):
        return bool(self._installer_path)

    @Property(str, notify=changed)
    def installerPath(self):
        return self._installer_path

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property(str, notify=changed)
    def versions(self):
        return self._versions

    @Property(int, notify=changed)
    def progress(self):
        return self._progress

    @Property(bool, notify=changed)
    def indeterminate(self):
        return self._indeterminate

    @Property(str, constant=True)
    def releasesUrl(self):
        return RELEASES_URL

    @Slot()
    def check(self):
        self._available = False
        self._installer_path = ""
        self.asset = None
        self._versions = f"Installed: {APP_VERSION}"
        self._status = "Checking for updates…"
        self._progress = 0
        self._indeterminate = True
        self._busy = True
        self.changed.emit()
        worker = UpdateWorker(parent=self)
        worker.releaseFetched.connect(self.release_fetched)
        worker.finished.connect(self.worker_finished)
        self.workers.append(worker)
        worker.start()

    @Slot(str, bool, object)
    def release_fetched(self, latest, available, asset):
        self._versions = f"Installed: {APP_VERSION} · Latest: {latest}"
        self._available = available
        self.asset = asset
        self._status = "Update available" if available else "Up to date"
        self._indeterminate = False
        self.changed.emit()

    @Slot()
    def download(self):
        self._busy = True
        self._status = "Downloading update…"
        self._progress = 0
        self._indeterminate = True
        self.changed.emit()
        worker = UpdateWorker(self.asset, self)
        worker.downloadProgress.connect(self.download_progress)
        worker.downloaded.connect(self.downloaded)
        worker.finished.connect(self.worker_finished)
        self.workers.append(worker)
        worker.start()

    @Slot(object, object)
    def download_progress(self, current, total):
        self._indeterminate = current == 0
        self._progress = round(current / total * 1000)
        self.changed.emit()

    @Slot(str)
    def downloaded(self, path):
        self._installer_path = path
        self._status = "Download complete. Quit and install when ready."
        self._progress = 1000
        self._indeterminate = False
        self.changed.emit()

    @Slot()
    def worker_finished(self):
        worker = self.sender()
        self.workers.remove(worker)
        worker.deleteLater()
        self._busy = False
        self.changed.emit()
