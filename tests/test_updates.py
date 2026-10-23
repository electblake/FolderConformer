import io
import json
import tempfile
import threading
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QMetaObject, QObject, QThread, QTimer, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from folderconformer import app, updates


APP = QApplication.instance() or QApplication([])


class UpdateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.asset = {
            "name": "FolderConformer-0.10.0-windows-amd64-Setup.exe",
            "size": 600000,
            "browser_download_url": "https://example.test/installer.exe",
        }
        self.release = {"tag_name": "v0.10.0", "name": "FolderConformer 0.10.0", "published_at": "2026-10-23T12:00:00Z", "assets": [
            {**self.asset, "name": "FolderConformer-0.10.0-windows-arm64-Setup.exe"}, self.asset,
        ]}
        for name, value in (("APP_VERSION", "0.3.0"), ("platform.system", lambda: "Windows"),
                            ("platform.machine", lambda: "AMD64")):
            mock = patch("folderconformer.updates." + name, value)
            mock.start()
            self.addCleanup(mock.stop)
        config = patch("folderconformer.app.user_config_path", return_value=self.directory / "config")
        config.start()
        self.addCleanup(config.stop)

    def wait_for(self, predicate):
        for _ in range(300):
            APP.processEvents()
            if predicate():
                return
            QTest.qWait(10)
        self.fail("Timed out waiting for update worker")

    def open_dialog(self, controller):
        engine = QQmlApplicationEngine()
        engine.addImageProvider("standard", app.StandardIconProvider())
        messages = []
        engine.warnings.connect(lambda warnings: messages.extend(w.toString() for w in warnings))
        engine.setInitialProperties({"controller": controller})
        engine.load(QUrl.fromLocalFile(str(Path(app.__file__).parent / "qml/Main.qml")))
        window = engine.rootObjects()[0]
        window.quitRequested.connect(window.close)
        self.addCleanup(lambda: (window.close(), engine.clearComponentCache()))
        menu = window.findChild(QObject, "checkForUpdatesMenu")
        self.assertEqual(menu.property("text"), "Check for updates..")
        QMetaObject.invokeMethod(menu, "triggered")
        dialog = window.findChild(QObject, "softwareUpdate")
        APP.processEvents()
        self.assertIsNotNone(dialog)
        self.assertEqual(messages, [])
        return engine, window, dialog

    def button(self, dialog, name):
        return dialog.findChild(QObject, name)

    def assert_buttons(self, dialog, check, download, install, close):
        for name, enabled in (("checkForUpdates", check), ("viewReleases", check),
                              ("downloadUpdate", download), ("installUpdate", install), ("closeUpdate", close)):
            self.assertEqual(self.button(dialog, name).property("enabled"), enabled, name)

    def test_numeric_ordering(self):
        self.assertGreater(updates.version_tuple("0.10.0"), updates.version_tuple("0.9.9"))
        self.assertGreater(updates.version_tuple("1.0.0"), updates.version_tuple("0.99.99"))
        self.assertEqual(updates.version_tuple("0.3.0"), updates.version_tuple("0.3.0"))

    def test_installer_helper_waits_for_full_process_exit(self):
        import _winapi

        ready = self.directory / "waiting.txt"
        launched = self.directory / "launched.txt"
        script = r'''
import base64
import subprocess
import sys
from unittest.mock import patch
from folderconformer.updates import install_after_exit

launch = subprocess.Popen
def capture(args, **kwargs):
    command = base64.b64decode(args[-1]).decode("utf-16-le")
    assert "Start-Process -FilePath 'C:/cache/installer''s setup.exe'" in command
    command = command.replace("$null = $wait.WaitOne()", "Set-Content -LiteralPath '" + sys.argv[1] + "' -Value waiting; $null = $wait.WaitOne()")
    command = command.replace("Start-Process -FilePath 'C:/cache/installer''s setup.exe'", "Set-Content -LiteralPath '" + sys.argv[2] + "' -Value installed")
    args[-1] = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    return launch(args, **kwargs)

with patch("folderconformer.updates.subprocess.Popen", side_effect=capture):
    helper = install_after_exit("C:/cache/installer's setup.exe")
print(helper.pid, flush=True)
sys.stdin.readline()
'''
        parent = subprocess.Popen([sys.executable, "-c", script, str(ready), str(launched)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: parent.poll() is None and parent.kill())
        helper_pid = int(parent.stdout.readline())
        handle = _winapi.OpenProcess(0x00100000, False, helper_pid)
        self.addCleanup(_winapi.CloseHandle, handle)
        self.wait_for(ready.exists)
        self.assertFalse(launched.exists())
        self.assertIsNone(parent.poll())
        parent.communicate("exit\n", timeout=10)
        self.assertEqual(parent.returncode, 0)
        self.assertEqual(_winapi.WaitForSingleObject(handle, 10000), 0)
        self.assertEqual(launched.read_text().strip(), "installed")

    def test_check_headers_timeout_exact_asset_and_thread_delivery(self):
        updater = updates.Updates()
        network_threads = []
        signal_threads = []

        def response(request, timeout):
            network_threads.append(QThread.currentThread())
            self.assertEqual(request.full_url, "https://api.github.com/repos/electblake/folderconformer/releases/latest")
            self.assertEqual(request.get_header("Accept"), "application/vnd.github+json")
            self.assertEqual(request.get_header("User-agent"), "FolderConformer/0.3.0")
            self.assertEqual(request.get_header("X-github-api-version"), updates.GITHUB_API_VERSION)
            self.assertEqual(timeout, 30)
            return io.BytesIO(json.dumps(self.release).encode())

        updater.changed.connect(lambda: signal_threads.append(QThread.currentThread()))
        with patch("folderconformer.updates.urlopen", side_effect=response):
            updater.check()
            self.assertTrue(updater.busy)
            self.assertTrue(updater.indeterminate)
            self.wait_for(lambda: not updater.workers)
        self.assertEqual(updater.versions, "Installed: 0.3.0 · Latest: 0.10.0")
        self.assertEqual(updater.releaseInfo, "FolderConformer 0.10.0 · Published 2026-10-23T12:00:00Z")
        self.assertEqual(updater.status, "Update available")
        self.assertEqual(updater.asset, self.asset)
        self.assertTrue(updater.available)
        self.assertFalse(updater.ready)
        self.assertNotEqual(network_threads, [APP.thread()])
        self.assertTrue(all(thread == APP.thread() for thread in signal_threads))

    def test_not_newer_and_each_check_resets_installer_state(self):
        updater = updates.Updates()
        for latest in ("v0.3.0", "v0.2.9"):
            updater._available = True
            updater._installer_path = "old.exe"
            updater.asset = self.asset
            with patch("folderconformer.updates.urlopen", return_value=io.BytesIO(json.dumps({
                "tag_name": latest, "assets": [], "name": latest, "published_at": "2026-10-23T12:00:00Z",
            }).encode())):
                updater.check()
                self.assertFalse(updater.available)
                self.assertFalse(updater.ready)
                self.assertEqual(updater.installerPath, "")
                self.assertIsNone(updater.asset)
                self.wait_for(lambda: not updater.workers)
            self.assertEqual(updater.status, "Up to date")

    def test_missing_exact_asset_surfaces(self):
        self.release["assets"].pop()
        with patch("folderconformer.updates.urlopen", return_value=io.BytesIO(json.dumps(self.release).encode())):
            with self.assertRaises(StopIteration):
                updates.UpdateWorker().run()

    def test_stream_chunks_progress_and_cache_filename(self):
        class Download(io.BytesIO):
            def read(self, size):
                self.read_sizes.append(size)
                return super().read(size)

        body = b"x" * self.asset["size"]
        response = Download(body)
        response.read_sizes = []
        worker = updates.UpdateWorker(self.asset)
        progress = []
        paths = []
        worker.downloadProgress.connect(lambda current, total: progress.append((current, total)))
        worker.downloaded.connect(paths.append)
        with patch("folderconformer.updates.urlopen", return_value=response) as request, patch(
            "folderconformer.updates.user_cache_path", return_value=self.directory,
        ) as cache:
            worker.run()
        cache.assert_called_once_with("FolderConformer", appauthor=False)
        request.assert_called_once_with(self.asset["browser_download_url"], timeout=30)
        self.assertEqual(response.read_sizes, [256 * 1024] * 4)
        self.assertEqual(progress, [(262144, 600000), (524288, 600000), (600000, 600000)])
        path = self.directory / "updates" / self.asset["name"]
        self.assertEqual(paths, [str(path)])
        self.assertEqual(path.read_bytes(), body)

    def test_dialog_busy_dismissal_progress_buttons_and_ordinary_close(self):
        entered = threading.Event()
        release_network = threading.Event()
        ticks = []

        def response(*args, **kwargs):
            entered.set()
            release_network.wait(5)
            return io.BytesIO(json.dumps(self.release).encode())

        controller = app.Controller()
        updater = controller.updates
        with patch("folderconformer.updates.urlopen", side_effect=response):
            engine, window, dialog = self.open_dialog(controller)
            self.wait_for(entered.is_set)
            QTimer.singleShot(0, lambda: ticks.append(True))
            APP.processEvents()
            self.assertEqual(ticks, [True])
            self.assertEqual(dialog.modality(), Qt.WindowModality.WindowModal)
            self.assertEqual(dialog.minimumWidth(), 460)
            self.assert_buttons(dialog, False, False, False, False)
            self.assertFalse(window.findChild(QObject, "conformerScreen").property("enabled"))
            self.assertTrue(self.button(dialog, "updateProgress").property("indeterminate"))
            self.assertFalse(dialog.close())
            self.assertFalse(window.close())
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
            self.assertTrue(dialog.isVisible())
            release_network.set()
            self.wait_for(lambda: not updater.workers)
        self.assert_buttons(dialog, True, True, False, True)
        self.assertTrue(window.findChild(QObject, "conformerScreen").property("enabled"))

        entered.clear()
        release_network.clear()

        def download(*args, **kwargs):
            entered.set()
            release_network.wait(5)
            return io.BytesIO(b"x" * self.asset["size"])

        with patch("folderconformer.updates.urlopen", side_effect=download), patch(
            "folderconformer.updates.user_cache_path", return_value=self.directory,
        ):
            QMetaObject.invokeMethod(self.button(dialog, "downloadUpdate"), "clicked")
            self.wait_for(entered.is_set)
            self.assert_buttons(dialog, False, False, False, False)
            self.assertFalse(dialog.close())
            updater.download_progress(150000, 600000)
            progress = self.button(dialog, "updateProgress")
            self.assertFalse(progress.property("indeterminate"))
            self.assertEqual(progress.property("to"), 1000)
            self.assertEqual(progress.property("value"), 250)
            release_network.set()
            self.wait_for(lambda: not updater.workers)
        self.assert_buttons(dialog, True, False, True, True)
        self.assertEqual(updater.status, "Download complete")
        self.assertEqual(progress.property("value"), 1000)
        with patch("folderconformer.app.install_after_exit") as launch:
            QMetaObject.invokeMethod(self.button(dialog, "closeUpdate"), "clicked")
            APP.processEvents()
            self.assertFalse(dialog.isVisible())
            self.assertIsNone(window.property("pending_installer"))
            self.assertTrue(window.isVisible())
            launch.assert_not_called()
        window.close()

    def test_install_records_path_and_requests_normal_shutdown(self):
        controller = app.Controller()
        with patch("folderconformer.updates.urlopen", return_value=io.BytesIO(json.dumps(self.release).encode())):
            engine, window, dialog = self.open_dialog(controller)
            self.wait_for(lambda: not controller.updates.workers)
        controller.updates._installer_path = "C:/cache/installer.exe"
        controller.updates.changed.emit()
        with patch("folderconformer.app.install_after_exit") as launch:
            QMetaObject.invokeMethod(self.button(dialog, "installUpdate"), "clicked")
            APP.processEvents()
            self.assertEqual(window.property("pending_installer"), "C:/cache/installer.exe")
            self.assertFalse(window.isVisible())
            self.assertFalse(dialog.isVisible())
            launch.assert_not_called()

    def test_bootstrap_launches_only_after_event_loop_returns(self):
        for installer in (None, "C:/cache/installer.exe"):
            events = []
            host = self.enterContext(patch.object(app, "MainWindow")).return_value
            host.destroy.side_effect = lambda: events.append("native resources released")
            host.deleteLater.side_effect = lambda: events.append("widgets deleted")
            application = MagicMock()
            callbacks = []
            application.aboutToQuit.connect.side_effect = callbacks.append
            application.exec.side_effect = lambda: (callbacks[0](), events.append("event loop returned"), 42)[2]
            engine = MagicMock()
            engine.deleteLater.side_effect = lambda: events.append("engine deleted")
            engine.rootObjects.return_value[0].property.return_value = installer
            with patch("folderconformer.app.QApplication", return_value=application), patch(
                "folderconformer.app.QQmlApplicationEngine", return_value=engine,
            ), patch("folderconformer.app.Controller", return_value=MagicMock(theme="", restart_requested=False)), patch("folderconformer.app.sys.argv", ["folderconformer"]), patch(
                "folderconformer.app.install_after_exit", side_effect=lambda path: events.append(path),
            ) as launch:
                self.assertEqual(app.main(), 42)
                self.assertEqual(events, ["native resources released", "widgets deleted", "engine deleted", "event loop returned"]
                                 + ([installer] if installer is not None else []))
                self.assertEqual(launch.call_count, int(installer is not None))

    def test_real_app_exits_cleanly_with_embedded_widgets(self):
        script = r'''
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from folderconformer import app

config = Path(sys.argv[1])
app.user_config_path = lambda *args, **kwargs: config
sys.argv = [sys.argv[0]]
class Window(app.MainWindow):
    def __init__(self, controller, quick_window):
        super().__init__(controller, quick_window)
        QTimer.singleShot(100, self.float_preview)

    def float_preview(self):
        self.preview_dock.setFloating(True)
        QTimer.singleShot(100, self.close)

app.MainWindow = Window
sys.exit(app.main())
'''
        for _ in range(2):
            result = subprocess.run([sys.executable, "-X", "faulthandler", "-c", script, str(self.directory)],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_restart_launches_after_event_loop_returns(self):
        self.enterContext(patch.object(app, "MainWindow"))
        events = []
        application = MagicMock()
        callbacks = []
        application.aboutToQuit.connect.side_effect = callbacks.append
        application.exec.side_effect = lambda: (callbacks[0](), events.append("quit"), 0)[2]
        engine = MagicMock()
        engine.rootObjects.return_value[0].property.return_value = None
        with patch.object(app, "QApplication", return_value=application), patch.object(
            app, "QQmlApplicationEngine", return_value=engine,
        ), patch.object(app, "Controller", return_value=MagicMock(theme="", restart_requested=True)), patch.object(
            app.sys, "argv", ["folderconformer"],
        ), patch.object(app.subprocess, "Popen", side_effect=lambda args: events.append(args)):
            self.assertEqual(app.main(), 0)
        self.assertEqual(events, ["quit", [app.sys.executable, "-I", "-m", "folderconformer"]])
