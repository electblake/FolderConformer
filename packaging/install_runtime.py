import os
import subprocess
import sys
import tarfile
from pathlib import Path

from platformdirs import user_cache_path, user_data_path


source = Path(sys.argv[1])
uv = sys.argv[2]
model = Path(sys.argv[3])
runtime = user_data_path("FolderConformer", appauthor=False) / "runtime"
environment = os.environ | {
    "UV_PROJECT_ENVIRONMENT": str(runtime / "venv"),
    "UV_CACHE_DIR": str(user_cache_path("FolderConformer", appauthor=False) / "uv"),
    "UV_LINK_MODE": "copy",
    "UV_HTTP_RETRIES": "0",
}
subprocess.run([
    uv, "sync", "--project", str(source), "--locked", "--no-default-groups",
    "--no-editable", "--python", "3.12.10", "--managed-python",
], env=environment, check=True)
with tarfile.open(model) as archive:
    archive.extractall(runtime / "venv/models/yamnet/1", filter="data")
subprocess.run([
    str(runtime / "venv/Scripts/python.exe"), "-I", "-c",
    "from static_ffmpeg.run import get_or_fetch_platform_executables_else_raise; "
    "get_or_fetch_platform_executables_else_raise()",
], env=environment, check=True)
print(f"Installed FolderConformer runtime: {runtime}", flush=True)
subprocess.run([
    str(runtime / "venv/Scripts/python.exe"), "-I", "-c",
    "from folderconformer.music import MusicDetector; import numpy as np; "
    "detector = MusicDetector(); "
    "print('YAMNet setup inference:', detector.model(np.zeros(16000, dtype=np.float32))[0].shape)",
], env=environment, check=True)
