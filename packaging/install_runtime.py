import os
import subprocess
import sys
from pathlib import Path

from platformdirs import user_cache_path, user_data_path


source = Path(sys.argv[1])
uv = sys.argv[2]
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
subprocess.run([
    str(runtime / "venv/Scripts/python.exe"), "-I", "-c",
    "from static_ffmpeg.run import get_or_fetch_platform_executables_else_raise; "
    "get_or_fetch_platform_executables_else_raise()",
], env=environment, check=True)
print(f"Installed FolderConformer runtime: {runtime}", flush=True)
