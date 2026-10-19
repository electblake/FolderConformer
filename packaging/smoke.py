import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QProcess, QProcessEnvironment


root = Path(__file__).resolve().parent.parent
environment = os.environ.copy()
environment["PATH"] = str(Path(os.environ["SYSTEMROOT"]) / "System32")
environment["PYTHONIOENCODING"] = "utf-8"
for key in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH", "QML_IMPORT_PATH"):
    environment.pop(key, None)

app = QCoreApplication([])
with tempfile.TemporaryDirectory(prefix="FolderConformer-smoke-") as temporary:
    stage = Path(temporary) / "app"
    shutil.copytree(root / "dist/FolderConformer", stage)
    folder = Path(temporary) / "日本語 media"
    folder.mkdir()
    for directory, filename in (("images", "legacy-photo.bin"), ("videos", "legacy-video.bin"),
                                ("jpg", "photo.bin"), ("mp4", "movie.bin")):
        (folder / directory).mkdir()
        (folder / directory / filename).write_bytes(b"preserved")
    subprocess.run([
        str(stage / "_internal/tools/ffmpeg.exe"), "-v", "error", "-f", "lavfi", "-i",
        "color=s=80x40:d=0.1", "-frames:v", "1", str(folder / "wide.png"),
    ], check=True, env=environment)
    result = subprocess.run([
        str(stage / "FolderConformer.exe"), "--worker", str(folder),
        json.dumps([{"id": rule_id, "enabled": True} for rule_id in (
            "landscape", "extension", "rename_images", "rename_videos", "photo_extensions", "video_extensions",
        )]), "Landscape-FULL",
    ], check=True, stdout=subprocess.PIPE, encoding="utf-8", env=environment, cwd=temporary)
    assert (folder / "Landscape-FULL/png/wide.png").is_file()
    for name in ("photo/legacy-photo.bin", "video/legacy-video.bin", "photo/jpg/photo.bin", "video/mp4/movie.bin"):
        assert (folder / name).read_bytes() == b"preserved"
    assert "Completed: 1 files processed, 1 files moved, 2 folders renamed, 2 folders moved." in result.stdout
    recursive_folder = Path(temporary) / "recursive"
    (recursive_folder / "nested/deep").mkdir(parents=True)
    (recursive_folder / "nested/deep/note.txt").write_text("nested content")
    subprocess.run([
        str(stage / "FolderConformer.exe"), "--worker", str(recursive_folder),
        json.dumps([{"id": "extension", "enabled": True}]), "Landscape-FULL", "--recursive",
    ], check=True, stdout=subprocess.PIPE, env=environment, cwd=temporary)
    assert (recursive_folder / "txt/note.txt").read_text() == "nested content"
    process = QProcess()
    qt_environment = QProcessEnvironment()
    for key, value in environment.items():
        qt_environment.insert(key, value)
    process.setProcessEnvironment(qt_environment)
    process.setWorkingDirectory(temporary)
    process.start(str(stage / "FolderConformer.exe"))
    assert process.waitForStarted(10000)
    assert not process.waitForFinished(1800), bytes(process.readAllStandardError()).decode("utf-8")
    process.terminate()
    process.waitForFinished(10000)
    errors = bytes(process.readAllStandardError()).decode("utf-8")
    assert not errors, errors
print("Relocated frozen worker and GUI passed with developer paths removed.")
