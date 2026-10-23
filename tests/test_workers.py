import contextlib
import io
import re
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock, get_ident
from unittest.mock import patch

from folderconformer.pipeline import RunControl, conform
from folderconformer.workers import DEFAULT_WORKER_THREADS, MusicAnalysis, worker_results


class WorkerTests(unittest.TestCase):
    def test_parallel_analysis_keeps_moves_ordered_and_conflicts_safe(self):
        for rule, directory, suffix in (("landscape", "video", "mp4"), ("landscape_images", "photo", "png")):
            with self.subTest(rule=rule), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                media = root / directory
                (media / "Wide").mkdir(parents=True)
                for name in ("a", "b", "c"):
                    (media / f"{name}.{suffix}").write_text(name)
                (media / "Wide" / f"a.{suffix}").write_text("original")
                barrier = Barrier(3)
                workers = set()
                lock = Lock()
                main_thread = get_ident()
                original_rename = Path.rename
                moved = []

                def analyze(path, ffprobe):
                    with lock:
                        workers.add(get_ident())
                    barrier.wait(timeout=5)
                    return True

                def rename(source, target):
                    self.assertEqual(get_ident(), main_thread)
                    moved.append(source.name)
                    return original_rename(source, target)

                output = io.StringIO()
                with patch("folderconformer.pipeline.is_landscape", side_effect=analyze), \
                        patch.object(Path, "rename", rename), contextlib.redirect_stdout(output):
                    conform(root, [{"id": rule, "enabled": True}], "Wide", Path("ffprobe"),
                            "video", "photo", "mp4", "png", "Data", "txt", enumerate_conflicts=True,
                            worker_threads=DEFAULT_WORKER_THREADS | {rule: 3})
                self.assertEqual(len(workers), 3)
                self.assertEqual(moved, [f"{name}.{suffix}" for name in ("a", "b", "c")])
                self.assertEqual((media / "Wide" / f"a.{suffix}").read_text(), "original")
                self.assertEqual((media / "Wide" / f"a_1.{suffix}").read_text(), "a")
                lines = output.getvalue().splitlines()
                identifier = "H2" if rule == "landscape" else "B7"
                for line in lines:
                    if not line.startswith("Completed: "):
                        self.assertRegex(line, rf"^(?:\[\d+/\d+\] )?\[{identifier}\] ")
                progress = [line for line in lines if re.match(r"\[\d+/\d+\]", line)]
                self.assertEqual([line.split()[0] for line in progress], ["[1/3]", "[2/3]", "[3/3]"])

    def test_parallel_failure_propagates_without_moving_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "video").mkdir()
            (root / "video/bad.mp4").touch()
            with patch("folderconformer.pipeline.is_landscape", side_effect=ValueError("bad media")), \
                    contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "bad media"):
                conform(root, [{"id": "landscape", "enabled": True}], "Wide", Path("ffprobe"),
                        "video", "photo", "mp4", "png", "Data", "txt",
                        worker_threads=DEFAULT_WORKER_THREADS | {"landscape": 3})
            self.assertTrue((root / "video/bad.mp4").is_file())

    def test_stop_is_latched_and_stdin_handshake_is_serial(self):
        control = RunControl()
        barrier = Barrier(4)

        def checkpoint(_):
            barrier.wait(timeout=5)
            return control.checkpoint()

        output = io.StringIO()
        with patch("sys.stdin", io.StringIO("continue\nstop\n")), contextlib.redirect_stdout(output):
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(checkpoint, range(4)))
        self.assertEqual(sorted(results), [False, False, False, True])
        self.assertTrue(control.stopped)
        self.assertEqual(output.getvalue().splitlines(), ["Control: ready", "Control: ready"])

    def test_music_detectors_are_owned_and_reused_by_individual_threads(self):
        barrier = Barrier(3)
        owners = []
        lock = Lock()
        test = self

        class Detector:
            def __init__(self, classes):
                self.owner = get_ident()
                with lock:
                    owners.append(self.owner)

            def classify_video(self, path, ffprobe, control):
                test.assertEqual(get_ident(), self.owner)
                barrier.wait(timeout=5)
                return path

        with patch("folderconformer.music.MusicDetector", Detector):
            analysis = MusicAnalysis([], Path("ffprobe"))
            with worker_results(analysis, range(6), 3) as results:
                self.assertEqual(list(results), [(i, i) for i in range(6)])
        self.assertEqual(len(owners), 3)
        self.assertEqual(len(set(owners)), 3)

    def test_early_exit_still_surfaces_in_flight_failure(self):
        def work(value):
            if value == 1:
                raise ValueError("worker failed")
            return value

        with self.assertRaisesRegex(ValueError, "worker failed"):
            with worker_results(work, range(2), 2) as results:
                next(results)
