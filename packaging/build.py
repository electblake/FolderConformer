import os
import subprocess
import tomllib
from pathlib import Path


root = Path(__file__).resolve().parent.parent
version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
subprocess.run([os.environ["ISCC_PATH"], "/Q", f"/DMyAppVersion={version}", "packaging/installer.iss"], cwd=root, check=True)
