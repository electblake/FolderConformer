import contextlib
import io
import json
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from folderconformer import pipeline


FFPROBE = shutil.which("ffprobe")


def png_bytes(width, height):
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data)))

    pixels = (b"\x00" + b"\xff\x00\x00" * width) * height
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


class LandscapeProbeTests(unittest.TestCase):
    def setUp(self):
        if os.name != "nt":
            self.enterContext(patch.object(subprocess, "CREATE_NO_WINDOW", 0, create=True))

    def probe(self, data):
        result = subprocess.CompletedProcess([], 0, stdout=json.dumps(data))
        with patch("folderconformer.pipeline.subprocess.run", return_value=result):
            return pipeline.is_landscape(Path("media.jpg"), Path("ffprobe"))

    def test_invalid_dimensions_are_reported_as_media_probe_errors(self):
        invalid = (
            {"width": 0, "height": 0},
            {"width": 1920, "height": 0},
            {"width": 0, "height": 1080},
            {"width": -1, "height": 1080},
            {"width": 1920, "height": -1},
            {"width": 1920},
            {"height": 1080},
            {},
            {"width": None, "height": 1080},
            {"width": "1920", "height": 1080},
            {"width": 1920, "height": "1080"},
            {"width": 1920.0, "height": 1080},
        )
        for stream in invalid:
            with self.subTest(stream=stream), self.assertRaises(pipeline.MediaProbeError):
                self.probe({"streams": [stream]})

    def test_missing_selected_stream_is_a_media_probe_error(self):
        for data in ({}, {"streams": []}):
            with self.subTest(data=data), self.assertRaises(pipeline.MediaProbeError):
                self.probe(data)

    def test_ffprobe_failure_is_a_media_probe_error(self):
        failure = subprocess.CalledProcessError(1, ["ffprobe", "bad.jpg"],
                                              stderr="Invalid data found when processing input")
        with patch("folderconformer.pipeline.subprocess.run", side_effect=failure), \
                self.assertRaises(pipeline.MediaProbeError):
            pipeline.is_landscape(Path("bad.jpg"), Path("ffprobe"))

    def test_invalid_json_is_a_media_probe_error(self):
        result = subprocess.CompletedProcess([], 0, stdout="not JSON")
        with patch("folderconformer.pipeline.subprocess.run", return_value=result), \
                self.assertRaises(pipeline.MediaProbeError):
            pipeline.is_landscape(Path("bad.jpg"), Path("ffprobe"))

    def test_valid_dimensions_aspect_ratio_and_rotation_preserve_classification(self):
        cases = (
            ({"width": 1920, "height": 1080}, True),
            ({"width": 1080, "height": 1920}, False),
            ({"width": 1080, "height": 1080}, True),
            ({"width": 40, "height": 80, "sample_aspect_ratio": "4:1"}, True),
            ({"width": 80, "height": 40, "sample_aspect_ratio": "1:4"}, False),
            ({"width": 80, "height": 40, "sample_aspect_ratio": "N/A"}, True),
            ({"width": 80, "height": 40, "sample_aspect_ratio": "0:1"}, True),
            ({"width": 80, "height": 40, "side_data_list": [{"rotation": 90}]}, False),
            ({"width": 80, "height": 40, "side_data_list": [{"rotation": -90}]}, False),
            ({"width": 80, "height": 40, "side_data_list": [{"rotation": 180}]}, True),
            ({"width": 40, "height": 80, "side_data_list": [{"rotation": 90}]}, True),
            ({"width": 40, "height": 40, "side_data_list": [{"rotation": 90}]}, True),
        )
        for stream, expected in cases:
            with self.subTest(stream=stream):
                self.assertIs(self.probe({"streams": [stream]}), expected)

    def test_missing_probe_and_unrelated_errors_still_propagate(self):
        for error in (FileNotFoundError("ffprobe missing"), ValueError("programming error")):
            with self.subTest(error=type(error).__name__), \
                    patch("folderconformer.pipeline.subprocess.run", side_effect=error), \
                    self.assertRaises(type(error)) as raised:
                pipeline.is_landscape(Path("media.jpg"), Path("ffprobe"))
            self.assertIs(raised.exception, error)

    def test_mixed_batch_preserves_bad_file_and_continues_for_each_rule_and_thread_count(self):
        for rule_id, directory, extension in (
                ("landscape", "video", "mp4"), ("landscape_images", "photo", "jpg")):
            for threads in (1, 3):
                with self.subTest(rule=rule_id, threads=threads), tempfile.TemporaryDirectory() as temporary:
                    media = Path(temporary) / directory
                    media.mkdir()
                    originals = {f"{name}.{extension}": name.encode() for name in ("a-wide", "b-bad", "c-wide")}
                    for name, content in originals.items():
                        (media / name).write_bytes(content)

                    def probe(command, **kwargs):
                        dimensions = (0, 0) if Path(command[-1]).stem == "b-bad" else (1920, 1080)
                        data = {"streams": [{"width": dimensions[0], "height": dimensions[1]}]}
                        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(data))

                    output = io.StringIO()
                    with patch("folderconformer.pipeline.subprocess.run", side_effect=probe), \
                            contextlib.redirect_stdout(output):
                        result = pipeline.conform_files(
                            media, [{"id": rule_id, "enabled": True}], "Wide", Path("ffprobe"),
                            extension, threads=threads)
                    self.assertEqual(result, (3, 2))
                    bad = media / f"b-bad.{extension}"
                    self.assertEqual(bad.read_bytes(), originals[bad.name])
                    self.assertFalse((media / "Wide" / bad.name).exists())
                    for name in (f"a-wide.{extension}", f"c-wide.{extension}"):
                        self.assertEqual((media / "Wide" / name).read_bytes(), originals[name])
                        self.assertFalse((media / name).exists())
                    identifier = "H2" if rule_id == "landscape" else "B7"
                    self.assertIn(str(bad), output.getvalue())
                    self.assertIn(f"[3/3] [{identifier}] c-wide.{extension}", output.getvalue())
                    diagnostic = next(line for line in output.getvalue().splitlines() if str(bad) in line)
                    self.assertTrue(diagnostic.startswith(f"[{identifier}] "), diagnostic)
                    self.assertIn("width=0, height=0", diagnostic)

    def test_check_reports_bad_for_unusable_media_without_changing_file(self):
        for rule_id, directory in (("landscape", "video"), ("landscape_images", "photo")):
            with self.subTest(rule=rule_id), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                target = root / directory / "Wide"
                target.mkdir(parents=True)
                bad = target / "bad.jpg"
                bad.write_bytes(b"unchanged")
                result = subprocess.CompletedProcess([], 0, stdout=json.dumps({"streams": [{"width": 0, "height": 0}]}))
                output = io.StringIO()
                with patch("folderconformer.pipeline.subprocess.run", return_value=result), \
                        contextlib.redirect_stdout(output):
                    status = pipeline.check_rule(root, rule_id, "video", "photo", "mp4", "jpg",
                                                 "Data", "txt", Path("ffprobe"), "Wide")
                self.assertEqual(status, "BAD")
                self.assertEqual(bad.read_bytes(), b"unchanged")
                self.assertIn(str(bad), output.getvalue())
                self.assertIn(f"[{'H2' if rule_id == 'landscape' else 'B7'}]", output.getvalue())

    def test_unrelated_worker_exception_is_not_silenced(self):
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary)
            bad = media / "bad.jpg"
            bad.write_bytes(b"unchanged")
            with patch("folderconformer.pipeline.is_landscape", side_effect=ValueError("programming error")), \
                    contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "programming error"):
                pipeline.conform_files(media, [{"id": "landscape_images", "enabled": True}],
                                       "Wide", Path("ffprobe"), "jpg", threads=3)
            self.assertEqual(bad.read_bytes(), b"unchanged")

    @unittest.skipUnless(FFPROBE, "ffprobe executable not available")
    def test_real_ffprobe_rejects_corrupt_jpeg_and_png_without_zero_division(self):
        with tempfile.TemporaryDirectory() as temporary:
            for suffix in ("jpg", "png"):
                with self.subTest(suffix=suffix):
                    bad = Path(temporary) / f"bad.{suffix}"
                    bad.write_bytes(b"not an image")
                    with self.assertRaises(pipeline.MediaProbeError):
                        pipeline.is_landscape(bad, Path(FFPROBE))

    @unittest.skipUnless(FFPROBE, "ffprobe executable not available")
    def test_real_ffprobe_mixed_image_batch_finishes_and_preserves_corrupt_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary)
            wide = png_bytes(8, 4)
            portrait = png_bytes(4, 8)
            (media / "a-wide.png").write_bytes(wide)
            bad = media / "b-bad.jpg"
            bad.write_bytes(b"not a jpeg")
            (media / "c-wide.png").write_bytes(wide)
            (media / "d-portrait.png").write_bytes(portrait)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                result = pipeline.conform_files(media, [{"id": "landscape_images", "enabled": True}],
                                                "Wide", Path(FFPROBE), "jpg;png", threads=3)
            self.assertEqual(result, (4, 2))
            self.assertEqual(bad.read_bytes(), b"not a jpeg")
            self.assertEqual((media / "Wide/a-wide.png").read_bytes(), wide)
            self.assertEqual((media / "Wide/c-wide.png").read_bytes(), wide)
            self.assertEqual((media / "d-portrait.png").read_bytes(), portrait)
            self.assertIn(str(bad), output.getvalue())
            self.assertIn("[4/4] [B7] d-portrait.png", output.getvalue())


if __name__ == "__main__":
    unittest.main()
