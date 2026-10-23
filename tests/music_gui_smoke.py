"""Exercise the installed GUI, real model, decoder, checks, and moves together."""
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QMetaObject, QObject, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from static_ffmpeg.run import get_platform_dir

from folderconformer import app


root = Path(__file__).resolve().parent.parent
qt = QApplication([])
with tempfile.TemporaryDirectory(prefix="FolderConformer-music-GUI-") as directory:
    work = Path(directory)
    video_folder = work / "media/video"
    video_folder.mkdir(parents=True)
    for name, fixture in (("music", "vibeace"), ("speech", "libri1")):
        subprocess.run([str(Path(get_platform_dir()) / "ffmpeg.exe"), "-v", "error",
                        "-f", "lavfi", "-i", "color=s=80x40:r=5", "-i",
                        str(root / f"build/music/fixtures/{fixture}.ogg"), "-t", "10",
                        "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-c:a", "aac",
                        str(video_folder / (name + ".mp4"))], check=True)
    source = video_folder / "music.mp4"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    with patch.object(app, "user_config_path", return_value=work / "config"):
        controller = app.Controller(str(video_folder.parent))
        output = []
        controller.output.connect(output.append)
        engine = QQmlApplicationEngine()
        engine.addImageProvider("standard", app.StandardIconProvider())
        engine.setInitialProperties({"controller": controller, "visible": False})
        engine.load(QUrl.fromLocalFile(str(Path(app.__file__).parent / "qml/Main.qml")))
        quick = engine.rootObjects()[0]
        host = app.MainWindow(controller, quick)
        host.show()
        host.resize(1300, 1000)
        QTest.qWait(100)
        host.folder_fields["musicVideoFolder"].textEdited.emit("Tunes")
        host.music_threshold.setValue(0.504)
        host.singing_threshold.setValue(0.85)
        host.humming_threshold.setValue(0.95)
        restored = app.Controller()
        assert (restored.musicThreshold, restored.singingThreshold, restored.hummingThreshold) == (0.504, 0.85, 0.95)
        assert app.Controller().musicVideoFolder == "Tunes"
        assert host.audio_dock.isVisible()
        assert host.audio_dock.y() >= host.files_dock.y() + host.files_dock.height()
        pending = [quick.contentItem()]
        controls = {}
        while pending:
            item = pending.pop()
            controls[item.objectName()] = item
            pending.extend(item.childItems())
        QMetaObject.invokeMethod(controls["music_videosCheck"], "clicked")
        assert controller.process.waitForFinished(60000), "Check did not finish"
        assert controller.process.exitCode() == 0, "".join(output)
        assert controller.checkStatuses["music_videos"] == "BAD"
        assert source.exists()
        QMetaObject.invokeMethod(controls["music_videosRunOnce"], "clicked")
        assert controller.process.waitForFinished(60000), "Run Once did not finish"
        assert controller.process.exitCode() == 0, "".join(output)
        moved = video_folder / "Tunes/music.mp4"
        assert hashlib.sha256(moved.read_bytes()).hexdigest() == digest
        assert not source.exists()
        assert (video_folder / "speech.mp4").exists()
        controller.checkRule("music_videos")
        assert controller.process.waitForFinished(60000)
        assert controller.process.exitCode() == 0, "".join(output)
        assert controller.checkStatuses["music_videos"] == "OK"
        shutil.copyfile(moved, source)
        host.enumerate_conflicts.click()
        for index, rule in enumerate(controller.rules):
            controller.setEnabled(index, rule["id"] == "music_videos")
        QMetaObject.invokeMethod(quick.findChild(QObject, "executeRules"), "clicked")
        assert controller.process.waitForFinished(60000)
        assert controller.process.exitCode() == 0, "".join(output)
        assert hashlib.sha256(moved.with_name("music_1.mp4").read_bytes()).hexdigest() == digest
        shutil.copyfile(moved, source)
        controller.start()
        controller.pause()
        for _ in range(300):
            QTest.qWait(100)
            if controller.runState == "paused":
                break
        assert controller.runState == "paused", "".join(output)
        assert source.exists()
        assert not host.music_threshold.isEnabled()
        controller.stop()
        assert controller.process.waitForFinished(60000)
        assert controller.process.exitCode() == 2, "".join(output)
        assert source.exists()
        controller.start()
        controller.cancel()
        assert controller.process.waitForFinished(60000)
        assert source.exists()
        QTest.qWait(100)
        host.grab().save(str(root / "build/music/installed-ui.png"))
        quick.grabWindow().save(str(root / "build/music/installed-rules.png"))
        host.close()
        (root / "build/music/gui-worker.log").write_text("".join(output), encoding="utf-8")
print("Installed GUI: real model Check, Run Once, Execute, custom folder, conflicts, pause/stop/cancel, speech unchanged: PASS")
