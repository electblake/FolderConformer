import runpy
import unittest
from pathlib import Path
from unittest.mock import patch

from platformdirs import user_cache_path, user_data_path


class InstallRuntimeTests(unittest.TestCase):
    def test_runtime_model_and_cache_follow_installer_identity(self):
        script = Path(__file__).resolve().parent.parent / "packaging/install_runtime.py"
        for name in ("FolderConformer", "FolderConformer-Smoke-test"):
            with self.subTest(name=name), \
                    patch("sys.argv", [str(script), "source", "uv.exe", "yamnet.tar.gz", name]), \
                    patch("subprocess.run") as run, patch("tarfile.open") as archive:
                runpy.run_path(str(script))
                runtime = user_data_path(name, appauthor=False) / "runtime"
                environment = run.call_args_list[0].kwargs["env"]
                self.assertEqual(environment["UV_PROJECT_ENVIRONMENT"], str(runtime / "venv"))
                self.assertEqual(environment["UV_CACHE_DIR"], str(user_cache_path(name, appauthor=False) / "uv"))
                archive.return_value.__enter__.return_value.extractall.assert_called_once_with(
                    runtime / "venv/models/yamnet/1", filter="data")
                for call in run.call_args_list[1:]:
                    self.assertEqual(call.args[0][0], str(runtime / "venv/Scripts/python.exe"))
                    self.assertTrue(call.kwargs["check"])
