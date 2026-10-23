import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from static_ffmpeg.run import get_platform_dir

from folderconformer.music import MusicDetector


root = Path(__file__).resolve().parent.parent
directory = root / "build/music/fixtures"
ffprobe = Path(get_platform_dir()) / "ffprobe.exe"
detector = MusicDetector()
results = []
started = time.perf_counter()
for fixture in json.loads((root / "tests/music-fixtures.json").read_text(encoding="utf-8")):
    if fixture["split"] != sys.argv[1]:
        continue
    audio = directory / (fixture["id"] + ".ogg")
    assert hashlib.sha256(audio.read_bytes()).hexdigest() == fixture["sha256"]
    video = audio.with_suffix(".mp4")
    subprocess.run([str(ffprobe.with_name("ffmpeg.exe")), "-nostdin", "-v", "error", "-y",
                    "-f", "lavfi", "-i", "color=s=80x40:r=5", "-i", str(audio),
                    "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-c:a", "aac",
                    "-shortest", str(video)], check=True)
    result = detector.classify_video(video, ffprobe)
    results.append({"id": fixture["id"], "label": fixture["label"],
                    "score": result.max_window_score, "detected": result.contains_music})
report = {"split": sys.argv[1], "thresholds": detector.thresholds,
          "elapsed_seconds": time.perf_counter() - started, "files": results}
output = root / f"build/music/{sys.argv[1]}-results.json"
output.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
