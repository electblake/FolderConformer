import csv
import json
import subprocess
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import tensorflow as tf

from folderconformer.music_model import MODEL_PATH, MODEL_VERSION, DEFAULT_AUDIO_CLASSES
from folderconformer.workers import report


SAMPLE_RATE = 16000
FRAME_SAMPLES = 15600
HOP_SAMPLES = 7680
BATCH_FRAMES = 8
BLOCK_SAMPLES = FRAME_SAMPLES + (BATCH_FRAMES - 1) * HOP_SAMPLES


@dataclass(frozen=True)
class MusicEvidence:
    stream: int
    channel: int
    start_s: float
    end_s: float
    label: str
    score: float


@dataclass(frozen=True)
class MusicDetection:
    contains_music: bool
    max_window_score: float
    thresholds: tuple[float, ...]
    evidence_windows: tuple[MusicEvidence, ...]
    model_version: str = MODEL_VERSION


class MusicDetector:
    def __init__(self, audio_classes=DEFAULT_AUDIO_CLASSES):
        self.thresholds = tuple(threshold for mid, threshold in audio_classes)
        self.model = tf.saved_model.load(str(MODEL_PATH))
        with open(self.model.class_map_path().numpy(), encoding="utf-8") as source:
            classes = list(csv.DictReader(source))
        self.columns = [next(int(row["index"]) for row in classes if row["mid"] == mid)
                        for mid, threshold in audio_classes]
        self.labels = [classes[index]["display_name"] for index in self.columns]

    def score_frames(self, blocks):
        """Score bounded (samples, channels) blocks on YAMNet's original frame grid."""
        pending = None
        start = 0
        for block in blocks:
            pending = block if pending is None else np.concatenate((pending, block))
            while len(pending) >= BLOCK_SAMPLES:
                scores = np.stack([self.model(pending[:BLOCK_SAMPLES, channel])[0].numpy()[:BATCH_FRAMES, self.columns]
                                   for channel in range(pending.shape[1])])
                yield start, start + BLOCK_SAMPLES, scores
                advance = BATCH_FRAMES * HOP_SAMPLES
                pending = pending[advance:]
                start += advance
        # The retained overlap is already covered. Only new real samples require
        # another prediction; the SavedModel pads the actual final context.
        if pending is not None and (start == 0 or len(pending) > FRAME_SAMPLES - HOP_SAMPLES):
            frames = max(1, 1 + (len(pending) - FRAME_SAMPLES + HOP_SAMPLES - 1) // HOP_SAMPLES)
            scores = np.stack([self.model(pending[:, channel])[0].numpy()[:frames, self.columns]
                               for channel in range(pending.shape[1])])
            yield start, start + len(pending), scores

    def classify_video(self, path: Path, ffprobe: Path, control=None):
        if not self.columns:
            return MusicDetection(False, 0.0, self.thresholds, ())
        probe = subprocess.run(
            [str(ffprobe), "-v", "error", "-select_streams", "a", "-show_streams", "-of", "json", str(path)],
            check=True, capture_output=True, text=True, encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        streams = json.loads(probe.stdout)["streams"]
        maximum = 0.0
        evidence = []
        for stream in streams:
            channels = stream["channels"]
            command = [str(ffprobe.with_name("ffmpeg.exe")), "-nostdin", "-v", "error", "-xerror",
                       "-i", str(path), "-map", f"0:{stream['index']}", "-vn", "-sn", "-dn",
                       "-ar", str(SAMPLE_RATE), "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"]
            with ExitStack() as resources:
                decoder = resources.enter_context(subprocess.Popen(
                    command, stdout=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW))
                resources.enter_context(decoder.stdout)
                resources.callback(decoder.kill)
                blocks = (np.frombuffer(data, dtype="<f4").reshape(-1, channels)
                          for data in iter(lambda: decoder.stdout.read(BLOCK_SAMPLES * channels * 4), b""))
                for start, end, scores in self.score_frames(blocks):
                    if control is not None and not control.checkpoint():
                        return None
                    maximum = max(maximum, float(scores.max()))
                    for channel, frame, label in np.argwhere(scores >= self.thresholds):
                        evidence.append(MusicEvidence(
                            stream["index"], int(channel), (start + frame * HOP_SAMPLES) / SAMPLE_RATE,
                            min(end, start + frame * HOP_SAMPLES + FRAME_SAMPLES) / SAMPLE_RATE,
                            self.labels[label], float(scores[channel, frame, label])))
                    report(f"[M5] Audio: {path.name}, stream {stream['index']}, {end / SAMPLE_RATE:.1f}s analyzed", flush=True)
                    if evidence:
                        return MusicDetection(True, maximum, self.thresholds, tuple(evidence))
                subprocess.CompletedProcess(command, decoder.wait()).check_returncode()
        return MusicDetection(False, maximum, self.thresholds, tuple(evidence))
