import json
import os
import platform
import subprocess
import tempfile
import tomllib
from pathlib import Path

from platformdirs import user_data_path
from PySide6.QtCore import QCoreApplication, QProcess, QProcessEnvironment


root = Path(__file__).resolve().parent.parent
version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
installer = root / "dist/installer" / (
    f"FolderConformer-{version}-{platform.system().lower()}-{platform.machine().lower()}-Setup.exe"
)
runtime = user_data_path("FolderConformer", appauthor=False) / "runtime"
assert not runtime.exists(), runtime
assert installer.stat().st_size < 5_000_000
app = QCoreApplication([])

with tempfile.TemporaryDirectory(prefix="FolderConformer-online-") as temporary:
    work = Path(temporary)
    install = work / "app"
    setup_environment = os.environ | {
        "UV_PYTHON_INSTALL_DIR": str(work / "managed-python"),
        "UV_CACHE_DIR": str(work / "bootstrap-cache"),
        "UV_HTTP_RETRIES": "0",
    }
    command = [str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/NOICONS", f"/DIR={install}"]
    subprocess.run([*command, f"/LOG={root / 'build/online-install.log'}"], env=setup_environment, check=True)
    python = runtime / "venv/Scripts/python.exe"
    pythonw = runtime / "venv/Scripts/pythonw.exe"
    environment = os.environ.copy()
    environment["PATH"] = str(Path(os.environ["SYSTEMROOT"]) / "System32")
    for key in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QML_IMPORT_PATH", "QML2_IMPORT_PATH"):
        environment.pop(key, None)
    installed_version = subprocess.run([
        str(python), "-I", "-c", "from importlib.metadata import version; print(version('folderconformer'))",
    ], env=environment, check=True, capture_output=True, text=True).stdout.strip()
    assert installed_version == version
    subprocess.run([
        str(python), "-I", str(root / "tests/test_integrations.py"), "-v",
    ], env=environment, cwd=work, check=True)
    media = work / "日本語 media"
    media.mkdir()
    for directory, filename in (("images", "photo.bin"), ("videos", "video.bin"),
                                ("jpg", "image.bin"), ("mp4", "movie.bin")):
        (media / directory).mkdir()
        (media / directory / filename).write_bytes(b"preserved")
    ffmpeg = subprocess.run([
        str(python), "-I", "-c", "from static_ffmpeg.run import get_platform_dir; "
        "from pathlib import Path; print(Path(get_platform_dir())/'ffmpeg.exe')",
    ], env=environment, check=True, capture_output=True, text=True).stdout.strip()
    subprocess.run([
        ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=s=80x40:d=0.1",
        "-frames:v", "1", str(media / "wide.png"),
    ], env=environment, check=True)
    rules = [{"id": rule_id, "enabled": True} for rule_id in (
        "landscape", "extension", "rename_images", "rename_videos", "photo_extensions", "video_extensions",
    )]
    result = subprocess.run([
        str(python), "-I", "-m", "folderconformer", "--worker", str(media), json.dumps(rules), "Landscape-FULL",
        "video/", "photo/", "mp4;ts;m4v;wmv;avi;mov;mkv;webm;mpg;mpeg;mts;m2ts;m2v;vob;flv;3gp;3g2;ogv;asf",
        "jpg;jpeg;png;webp;heic",
    ], env=environment, cwd=work, check=True, stdout=subprocess.PIPE, encoding="utf-8")
    assert (media / "Landscape-FULL/png/wide.png").is_file()
    for name in ("photo/photo.bin", "video/video.bin", "photo/jpg/image.bin", "video/mp4/movie.bin"):
        assert (media / name).read_bytes() == b"preserved"
    assert "2 folders renamed, 2 folders moved." in result.stdout
    process = QProcess()
    qt_environment = QProcessEnvironment()
    for key, value in environment.items():
        qt_environment.insert(key, value)
    process.setProcessEnvironment(qt_environment)
    process.setWorkingDirectory(str(work))
    process.start(str(pythonw), ["-I", "-m", "folderconformer"])
    assert process.waitForStarted(10000)
    assert not process.waitForFinished(1800), bytes(process.readAllStandardError()).decode("utf-8")
    subprocess.run(["taskkill", "/PID", str(process.processId()), "/T", "/F"], check=True, stdout=subprocess.PIPE)
    process.waitForFinished(10000)
    assert not bytes(process.readAllStandardError())
    subprocess.run([*command, f"/LOG={root / 'build/online-reinstall.log'}"], env=setup_environment, check=True)
    subprocess.run([str(install / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], check=True)
    assert not runtime.exists()
    assert not (install / "source").exists()
print(f"Online installer passed: {installer.stat().st_size:,} bytes; install, six rules, GUI, reinstall, uninstall.")
