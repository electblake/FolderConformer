import contextlib
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from static_ffmpeg.run import get_platform_dir

from folderconformer.music import BLOCK_SAMPLES, FRAME_SAMPLES, HOP_SAMPLES, MusicDetector
from folderconformer.music_model import MUSIC_THRESHOLD
from folderconformer.pipeline import RunControl, check_rule, conform


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "build/music/fixtures"
FFPROBE = Path(get_platform_dir()) / "ffprobe.exe"
FFMPEG = FFPROBE.with_name("ffmpeg.exe")
FOLDERS = ("video", "photo", "mp4;mkv", "png", "Data", "txt")


class MusicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector = MusicDetector()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "video").mkdir()

    def video(self, name, audio="vibeace", filters=None):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        command = [str(FFMPEG), "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=s=80x40:r=5"]
        if audio is not None:
            command += ["-i", str(FIXTURES / (audio + ".ogg")), "-map", "0:v", "-map", "1:a"]
        if filters:
            command += ["-af", filters]
        subprocess.run([*command, "-t", "10", "-c:v", "libx264", "-c:a", "aac", str(path)], check=True)
        return path

    def classify(self, path):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.detector.classify_video(path, FFPROBE)

    def run_music(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            conform(self.root, [{"id": "music_videos", "enabled": True}], "Wide", FFPROBE, *FOLDERS, **kwargs)

    def test_recording_hashes_match_published_sources(self):
        for row in json.loads((ROOT / "tests/music-fixtures.json").read_text(encoding="utf-8")):
            with self.subTest(recording=row["id"]):
                path = FIXTURES / (row["id"] + ".ogg")
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["sha256"])

    def test_real_music_and_speech_and_no_audio(self):
        for name, audio, expected in (("music", "vibeace", True), ("speech", "libri1", False),
                                      ("silent", None, False)):
            with self.subTest(name=name):
                result = self.classify(self.video(f"video/{name}.mp4", audio))
                self.assertEqual(result.contains_music, expected)
                self.assertEqual(result.thresholds, (MUSIC_THRESHOLD,) * 3)

    def test_chunked_predictions_match_whole_model_including_short_and_eof(self):
        data = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(FIXTURES / "vibeace.ogg"),
                               "-ar", "16000", "-ac", "1", "-f", "f32le", "pipe:1"],
                              check=True, capture_output=True).stdout
        samples = np.frombuffer(data, dtype="<f4")
        for length in (1, 4000, 8000, 15599, 15600, 15601, 23279, 23280, 23281,
                       BLOCK_SAMPLES - 1, BLOCK_SAMPLES, BLOCK_SAMPLES + 1,
                       BLOCK_SAMPLES + HOP_SAMPLES, 2 * BLOCK_SAMPLES + 127):
            with self.subTest(samples=length):
                waveform = samples[:length]
                expected = self.detector.model(waveform)[0].numpy()[:, self.detector.columns]
                # The exported model can round up an extra padded frame at exact
                # hop boundaries. Compare all contexts needed to cover real PCM.
                frames = max(1, 1 + (length - FRAME_SAMPLES + HOP_SAMPLES - 1) // HOP_SAMPLES)
                expected = expected[:frames]
                blocks = (waveform[i:i + 10003, None] for i in range(0, len(waveform), 10003))
                batches = list(self.detector.score_frames(blocks))
                actual = np.concatenate([scores[0] for start, end, scores in batches])
                np.testing.assert_allclose(actual, expected, atol=2e-5, rtol=1e-4)
                self.assertEqual(batches[-1][1], length)

    def test_opposite_polarity_and_single_channel_music(self):
        for name, expression in (("opposite", "pan=stereo|c0=c0|c1=-1*c0"),
                                  ("right", "pan=stereo|c0=0*c0|c1=c0")):
            result = self.classify(self.video(f"video/{name}.mp4", filters=expression))
            self.assertTrue(result.contains_music)
            self.assertIn(1, {window.channel for window in result.evidence_windows})

    def test_all_audio_streams_are_analyzed(self):
        path = self.root / "video/tracks.mkv"
        subprocess.run([str(FFMPEG), "-v", "error", "-f", "lavfi", "-i", "color=s=80x40:r=5",
                        "-i", str(FIXTURES / "libri1.ogg"), "-i", str(FIXTURES / "vibeace.ogg"),
                        "-map", "0:v", "-map", "1:a", "-map", "2:a", "-t", "8",
                        "-c:v", "libx264", "-c:a", "aac", str(path)], check=True)
        result = self.classify(path)
        self.assertTrue(result.contains_music)
        self.assertIn(2, {window.stream for window in result.evidence_windows})

    def test_music_at_end_and_under_speech(self):
        end = self.video("video/end.mp4", filters="atrim=0:2,adelay=8000:all=1")
        result = self.classify(end)
        self.assertTrue(result.contains_music)
        self.assertTrue(any(window.start_s >= 7 for window in result.evidence_windows))
        path = self.root / "video/mix.mp4"
        subprocess.run([str(FFMPEG), "-v", "error", "-f", "lavfi", "-i", "color=s=80x40:r=5",
                        "-i", str(FIXTURES / "libri1.ogg"), "-i", str(FIXTURES / "vibeace.ogg"),
                        "-filter_complex", "[1:a][2:a]amix=inputs=2:weights='1 0.5':normalize=0[a]",
                        "-map", "0:v", "-map", "[a]", "-t", "10", "-c:v", "libx264", "-c:a", "aac", str(path)], check=True)
        self.assertTrue(self.classify(path).contains_music)

    def test_threshold_equality_stops_at_first_qualifying_batch(self):
        path = self.video("video/music.mp4")
        result = self.classify(path)
        detector = MusicDetector(*([result.max_window_score] * 3))
        with contextlib.redirect_stdout(io.StringIO()):
            equal = detector.classify_video(path, FFPROBE)
        self.assertTrue(equal.contains_music)
        self.assertLessEqual(max(window.end_s for window in result.evidence_windows), BLOCK_SAMPLES / 16000)

    def test_each_class_uses_its_own_threshold(self):
        path = self.video("video/thresholds.mp4", filters="atrim=0:1,aformat=channel_layouts=stereo")
        decoded = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(path),
                                  "-ar", "16000", "-f", "f32le", "pipe:1"],
                                 check=True, capture_output=True).stdout
        waveform = np.frombuffer(decoded, dtype="<f4").reshape(-1, 2)
        batches = list(self.detector.score_frames([waveform]))
        maxima = batches[0][2].max(axis=(0, 1))
        for column, label in enumerate(self.detector.labels):
            with self.subTest(label=label):
                thresholds = [1.0, 1.0, 1.0]
                thresholds[column] = float(maxima[column]) / 2
                with patch.object(self.detector, "thresholds", tuple(thresholds)):
                    positive = self.classify(path)
                self.assertTrue(positive.contains_music)
                self.assertEqual({window.label for window in positive.evidence_windows}, {label})
                self.assertEqual(positive.thresholds, tuple(thresholds))
                thresholds[column] = float(maxima[column]) + 0.0001
                with patch.object(self.detector, "thresholds", tuple(thresholds)):
                    negative = self.classify(path)
                self.assertFalse(negative.contains_music)

    def test_positive_stops_decoder_and_skips_remaining_audio_tracks(self):
        path = self.root / "video/early.mkv"
        subprocess.run([str(FFMPEG), "-v", "error", "-f", "lavfi", "-i", "color=s=80x40:r=5",
                        "-stream_loop", "-1", "-i", str(FIXTURES / "vibeace.ogg"),
                        "-map", "0:v", "-map", "1:a", "-map", "1:a", "-t", "120",
                        "-c:v", "libx264", "-c:a", "aac", str(path)], check=True)
        processes = []
        popen = subprocess.Popen

        def record_process(*args, **kwargs):
            process = popen(*args, **kwargs)
            if args[0][0] == str(FFMPEG):
                processes.append(process)
            return process

        output = io.StringIO()
        with patch("folderconformer.music.subprocess.Popen", side_effect=record_process), contextlib.redirect_stdout(output):
            result = self.detector.classify_video(path, FFPROBE)
        self.assertTrue(result.contains_music)
        self.assertEqual(len(processes), 1)
        self.assertIsNotNone(processes[0].poll())
        self.assertTrue(processes[0].stdout.closed)
        self.assertEqual(output.getvalue().count("Audio:"), 1)
        self.assertIn("4.3s analyzed", output.getvalue())
        self.assertEqual({window.stream for window in result.evidence_windows}, {1})

    def test_negative_scans_through_end(self):
        path = self.video("video/speech.mp4", "libri1")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = self.detector.classify_video(path, FFPROBE)
        self.assertFalse(result.contains_music)
        self.assertGreaterEqual(output.getvalue().count("Audio:"), 3)
        self.assertIn("10.0s analyzed", output.getvalue())

    def test_actual_moves_checks_conflicts_and_repeat(self):
        positive = self.video("video/music.mp4")
        negative = self.video("video/speech.mp4", "libri1")
        original = hashlib.sha256(positive.read_bytes()).hexdigest()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check_rule(self.root, "music_videos", *FOLDERS, FFPROBE, "Wide"), "BAD")
        self.assertTrue(positive.exists())
        target = self.root / "video/With tunes/music.mp4"
        target.parent.mkdir()
        target.write_bytes(b"existing")
        self.run_music(music_folder="With tunes")
        self.assertTrue(positive.exists())
        self.assertEqual(target.read_bytes(), b"existing")
        self.run_music(music_folder="With tunes", enumerate_conflicts=True)
        moved = target.with_name("music_1.mp4")
        self.assertEqual(hashlib.sha256(moved.read_bytes()).hexdigest(), original)
        self.assertTrue(negative.exists())
        self.assertFalse(positive.exists())
        self.run_music(music_folder="With tunes", enumerate_conflicts=True)
        self.assertFalse(target.with_name("music_2.mp4").exists())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check_rule(self.root, "music_videos", *FOLDERS, FFPROBE, "Wide"), "OK")

    def test_rule_scope_excludes_photos_root_and_nested_video(self):
        path = self.video("video/music.mp4")
        for relative in ("root.mp4", "photo/music.mp4", "video/nested/music.mp4"):
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
        (self.root / "video/photo.png").write_bytes(b"photo must not be decoded")
        self.run_music()
        for relative in ("root.mp4", "photo/music.mp4", "video/nested/music.mp4", "video/photo.png"):
            self.assertTrue((self.root / relative).exists())

    def test_landscape_and_music_respect_order(self):
        original = self.video("original.mp4")
        for first, second, destination in (("music_videos", "landscape", "with-music"),
                                           ("landscape", "music_videos", "Wide")):
            source = self.root / "video" / (first + ".mp4")
            shutil.copyfile(original, source)
            with contextlib.redirect_stdout(io.StringIO()):
                conform(self.root, [{"id": first, "enabled": True}, {"id": second, "enabled": True}],
                        "Wide", FFPROBE, *FOLDERS)
            self.assertTrue((source.parent / destination / source.name).exists())

    def test_stop_during_analysis_preserves_current_video(self):
        source = self.video("video/music.mp4")
        control = RunControl()
        with patch("sys.stdin", io.StringIO("continue\nstop\n")):
            self.run_music(control=control)
        self.assertTrue(control.stopped)
        self.assertTrue(source.exists())
        self.assertFalse((source.parent / "with-music").exists())

    def test_decode_failure_surfaces_and_does_not_move(self):
        path = self.root / "video/broken.mp4"
        path.write_bytes(b"not a video")
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_music()
        self.assertTrue(path.exists())

    def test_missing_model_surfaces_from_tensorflow_without_downloading(self):
        with patch("folderconformer.music.MODEL_PATH", self.root / "missing-model"):
            with self.assertRaises(OSError):
                MusicDetector()


if __name__ == "__main__":
    unittest.main()
