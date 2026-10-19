import os
import subprocess
import sys
import tomllib
from pathlib import Path


root = Path(__file__).resolve().parent.parent
version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
subprocess.run([sys.executable, "-m", "PyInstaller", "packaging/FolderConformer.spec", "--noconfirm", "--clean"], cwd=root, check=True)
subprocess.run([sys.executable, "packaging/smoke.py"], cwd=root, check=True)
subprocess.run([os.environ["ISCC_PATH"], "/Q", f"/DMyAppVersion={version}", "packaging/installer.iss"], cwd=root, check=True)
