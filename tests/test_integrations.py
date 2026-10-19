import subprocess
import sys
import tempfile
import unittest
import winreg
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QEventLoop, QMetaObject, QObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine

from folderconformer import app, integrations


APP = QGuiApplication.instance() or QGuiApplication([])


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="FolderConformer Explorer ")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        config = patch("folderconformer.app.user_config_path", return_value=self.directory / "config")
        config.start()
        self.addCleanup(config.stop)

    def test_registry_commands_spaces_and_reinstallation(self):
        # Exercise real registry writes beneath a disposable test key.
        root = r"Software\FolderConformerTests\Explorer"
        contexts = tuple((root + "\\" + str(index), target)
                         for index, (_, target) in enumerate(integrations.CONTEXTS))
        executable = self.directory / "runtime with spaces/python.exe"
        for _ in range(2):
            with patch.object(integrations, "CONTEXTS", contexts), patch.object(sys, "executable", str(executable)):
                self.assertEqual(integrations.install(), 0)
            for context, target in contexts:
                menu = context + r"\FolderConformer"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, menu) as key:
                    self.assertEqual(winreg.QueryValueEx(key, "")[0], "Open in FolderConformer")
                    icon = winreg.QueryValueEx(key, "Icon")[0]
                    self.assertEqual(icon, f'"{Path(integrations.__file__).resolve().parent / "FolderConformer.ico"}"')
                    self.assertFalse(QIcon(icon.strip('"')).isNull())
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, menu + r"\command") as key:
                    command = winreg.QueryValueEx(key, "")[0]
                    self.assertEqual(command, " ".join(f'"{part}"' for part in (
                        str(executable.with_name("pythonw.exe").resolve()), "-I", "-m", "folderconformer", target,
                    )))
        for context, _ in contexts:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, context + r"\FolderConformer\command")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, context + r"\FolderConformer")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, context)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, root)

    def test_startup_folder_overrides_saved_folder_without_processing(self):
        saved = app.Controller()
        saved.folder = "previous folder"
        selected = str(self.directory / "selected folder")
        script = """
import sys
from pathlib import Path
from PySide6.QtCore import QTimer
from folderconformer import app
config = Path(sys.argv[2])
app.user_config_path = lambda *a, **k: config
original = app.QQmlApplicationEngine

def engine_factory():
    engine = original()
    load = engine.load
    def load_and_check(url):
        load(url)
        window = engine.rootObjects()[0]
        print(window.property("controller").folder)
        print(window.property("controller").running)
        QTimer.singleShot(0, app.QGuiApplication.quit)
    engine.load = load_and_check
    return engine

app.QQmlApplicationEngine = engine_factory
sys.argv = sys.argv[:2]
sys.exit(app.main())
"""
        result = subprocess.run([sys.executable, "-I", "-c", script, selected, str(self.directory / "config")],
                                check=True, capture_output=True, text=True)
        self.assertEqual(result.stdout.splitlines(), [selected, "False"])
        self.assertEqual(app.Controller().folder, selected)

    def test_install_worker_entrypoint(self):
        root = r"Software\FolderConformerTests\EntryPoint"
        contexts = tuple((root + "\\" + str(index), target)
                         for index, (_, target) in enumerate(integrations.CONTEXTS))
        script = (
            "import sys; from folderconformer import app,integrations; "
            f"integrations.CONTEXTS={contexts!r}; "
            "sys.argv=['folderconformer','--install-explorer']; raise SystemExit(app.main())"
        )
        result = subprocess.run([sys.executable, "-I", "-c", script],
                                check=True, capture_output=True, text=True)
        self.assertIn("[OK] Installed 3 File Explorer context menu entries.", result.stdout)
        for context, target in contexts:
            menu = context + r"\FolderConformer"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, menu + r"\command") as key:
                command = winreg.QueryValueEx(key, "")[0]
                self.assertIn(f'"{Path(sys.executable).with_name("pythonw.exe").resolve()}"', command)
                self.assertTrue(command.endswith(f'"{target}"'))
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, menu + r"\command")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, menu)
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, context)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, root)

    def test_extras_background_install_busy_and_success_only(self):
        controller = app.Controller()
        engine = QQmlApplicationEngine()
        messages = []
        engine.warnings.connect(lambda warnings: messages.extend(w.toString() for w in warnings))
        engine.setInitialProperties({"controller": controller})
        engine.load(QUrl.fromLocalFile(str(Path(app.__file__).parent / "qml/Main.qml")))
        window = engine.rootObjects()[0]
        menu = window.findChild(QObject, "extrasMenu")
        QMetaObject.invokeMethod(menu, "triggered")
        dialog = window.findChild(QObject, "extras")
        button = dialog.findChild(QObject, "installExplorer")
        status = dialog.findChild(QObject, "explorerStatus")
        loop = QEventLoop()
        results = []
        controller.explorerCompleted.connect(lambda code: (results.append(code), loop.quit()))
        # The real worker writes only disposable test keys in this test.
        worker = (
            "from folderconformer import integrations; "
            f"integrations.CONTEXTS=((r'Software\\FolderConformerTests\\Worker', '%1'),); "
            "raise SystemExit(integrations.install())"
        )
        with patch.object(controller.process, "setArguments", side_effect=lambda _: original_arguments(["-I", "-c", worker])):
            original_arguments = type(controller.process).setArguments.__get__(controller.process)
            QMetaObject.invokeMethod(button, "clicked")
        APP.processEvents()
        self.assertTrue(controller.running)
        self.assertFalse(button.property("enabled"))
        self.assertFalse(menu.property("enabled"))
        self.assertFalse(window.findChild(QObject, "inputFolder").property("enabled"))
        self.assertNotEqual(status.property("text"), "Installed in File Explorer")
        QTimer.singleShot(10000, loop.quit)
        loop.exec()
        APP.processEvents()
        self.assertEqual(results, [0])
        self.assertEqual(status.property("text"), "Installed in File Explorer")
        self.assertTrue(button.property("enabled"))
        self.assertTrue(menu.property("enabled"))
        controller.explorerCompleted.emit(1)
        self.assertNotEqual(status.property("text"), "Installed in File Explorer")
        self.assertEqual(messages, [])
        window.close()
        root = r"Software\FolderConformerTests\Worker\FolderConformer"
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, root + r"\command")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, root)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\FolderConformerTests\Worker")


if __name__ == "__main__":
    unittest.main()
