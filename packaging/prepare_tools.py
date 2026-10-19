import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from static_ffmpeg.run import get_or_fetch_platform_executables_else_raise


root = Path(__file__).resolve().parent.parent
tools = root / "build" / "tools"
tools.mkdir(parents=True, exist_ok=True)
executables = get_or_fetch_platform_executables_else_raise()
manifest = {"package": "static-ffmpeg==3.0", "architecture": "windows-x64", "files": {}}
for executable in executables:
    path = Path(executable)
    shutil.copy2(path, tools / path.name)
    with path.open("rb") as binary:
        manifest["files"][path.name] = hashlib.file_digest(binary, "sha256").hexdigest()
manifest["build"] = subprocess.run([executables[0], "-version"], check=True, capture_output=True, text=True).stdout
(tools / "provenance.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
