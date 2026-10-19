import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QGuiApplication

from folderconformer.pipeline import conform, is_landscape


ROOT = Path(__file__).resolve().parent.parent
FFMPEG = ROOT / "build/tools/ffmpeg.exe"
FFPROBE = ROOT / "build/tools/ffprobe.exe"
APP = QGuiApplication.instance() or QGuiApplication([])


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def media(self, name, size="80x40", *extra):
        path = self.folder / name
        subprocess.run([str(FFMPEG), "-v", "error", "-f", "lavfi", "-i",
                        f"color=c=red:s={size}:d=0.1", *extra, "-frames:v", "1", str(path)],
                       check=True, capture_output=True)
        return path

    def run_rules(self, rules, recursive=False):
        with contextlib.redirect_stdout(io.StringIO()):
            conform(self.folder, rules, "Landscape-FULL", FFPROBE, recursive=recursive)

    def test_summary_counts_folder_changes_when_no_files_are_scanned(self):
        for name in ("Images", "Videos", "jpg", "mp4"):
            (self.folder / name).mkdir()
        rules = [{"id": rule_id, "enabled": True} for rule_id in (
            "rename_images", "rename_videos", "photo_extensions", "video_extensions", "extension",
        )]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            conform(self.folder, rules, "Landscape-FULL", FFPROBE)
        lines = output.getvalue().splitlines()
        self.assertIn("[1/1] Renamed folder: Images \u2192 photo", lines)
        self.assertIn("[1/1] Renamed folder: Videos \u2192 video", lines)
        self.assertIn("[1/1] Moved folder: jpg \u2192 photo\\jpg", lines)
        self.assertIn("[1/1] Moved folder: mp4 \u2192 video\\mp4", lines)
        self.assertEqual([line for line in lines if line.startswith("Completed:")], [
            "Completed: 0 files processed, 0 files moved, 2 folders renamed, 2 folders moved.",
        ])

    def test_summary_counts_file_moves_and_folder_moves(self):
        (self.folder / "picture.jpg").write_text("picture")
        (self.folder / "note.txt").write_text("note")
        rules = [{"id": "extension", "enabled": True}, {"id": "photo_extensions", "enabled": True}]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            conform(self.folder, rules, "Landscape-FULL", FFPROBE)
        self.assertEqual(output.getvalue().splitlines()[-1],
                         "Completed: 2 files processed, 2 files moved, 0 folders renamed, 1 folders moved.")

    def test_folder_renames_are_case_insensitive_and_exact(self):
        for original, expected, rule_id in (
            ("ImAgE", "photo", "rename_images"), ("IMAGES", "photo", "rename_images"),
            ("ViDeO", "video", "rename_videos"), ("VIDEOS", "video", "rename_videos"),
        ):
            with self.subTest(original=original):
                source = self.folder / original
                (source / "nested").mkdir(parents=True)
                (source / "nested/keep.txt").write_text("kept")
                (self.folder / "images-backup").mkdir(exist_ok=True)
                self.run_rules([{"id": rule_id, "enabled": True}])
                target = self.folder / expected
                self.assertEqual((target / "nested/keep.txt").read_text(), "kept")
                self.assertEqual(target.name, next(p.name for p in self.folder.iterdir() if p.name.lower() == expected))
                (target / "nested/keep.txt").unlink()
                (target / "nested").rmdir()
                target.rmdir()
        self.assertTrue((self.folder / "images-backup").is_dir())

    def test_extension_folders_move_with_contents(self):
        photos = ("JPG", "jpeg", "png", "webp", "heic")
        videos = ("MP4", "ts", "m4v", "wmv", "avi", "mov", "mkv", "webm", "mpg", "mpeg",
                  "mts", "m2ts", "m2v", "vob", "flv", "3gp", "3g2", "ogv", "asf")
        for name in (*photos, *videos, "gif", "txt"):
            (self.folder / name / "nested").mkdir(parents=True)
            (self.folder / name / "nested/keep.txt").write_text(name)
        (self.folder / "jpg.txt").write_text("file")
        rules = [{"id": "photo_extensions", "enabled": True}, {"id": "video_extensions", "enabled": True}]
        self.run_rules(rules)
        self.run_rules(rules, recursive=True)
        for destination, names in (("photo", photos), ("video", videos), ("", ("gif", "txt"))):
            for name in names:
                self.assertEqual((self.folder / destination / name / "nested/keep.txt").read_text(), name)
        self.assertEqual((self.folder / "jpg.txt").read_text(), "file")

    def test_folder_rules_follow_file_rule_order(self):
        (self.folder / "first.JPG").write_text("first")
        rules = [{"id": "extension", "enabled": True}, {"id": "photo_extensions", "enabled": True}]
        self.run_rules(rules)
        self.assertEqual((self.folder / "photo/jpg/first.JPG").read_text(), "first")
        (self.folder / "second.PNG").write_text("second")
        self.run_rules(list(reversed(rules)))
        self.assertEqual((self.folder / "png/second.PNG").read_text(), "second")

    def test_recursive_folder_rules_and_disabled_rules(self):
        (self.folder / "nested/IMAGES/PNG").mkdir(parents=True)
        (self.folder / "nested/IMAGES/PNG/item.txt").write_text("content")
        rules = [{"id": "rename_images", "enabled": True}, {"id": "photo_extensions", "enabled": True}]
        self.run_rules(rules)
        self.assertTrue((self.folder / "nested/IMAGES/PNG/item.txt").is_file())
        self.run_rules([{"id": rule["id"], "enabled": False} for rule in rules], recursive=True)
        self.assertTrue((self.folder / "nested/IMAGES/PNG/item.txt").is_file())
        self.run_rules(rules, recursive=True)
        self.assertEqual((self.folder / "nested/photo/PNG/item.txt").read_text(), "content")

    def test_folder_collision_stops_without_merging(self):
        (self.folder / "images").mkdir()
        (self.folder / "images/incoming.txt").write_text("incoming")
        (self.folder / "photo").mkdir()
        (self.folder / "photo/existing.txt").write_text("existing")
        with self.assertRaises(FileExistsError):
            self.run_rules([{"id": "rename_images", "enabled": True}])
        self.assertEqual((self.folder / "images/incoming.txt").read_text(), "incoming")
        self.assertEqual((self.folder / "photo/existing.txt").read_text(), "existing")

    def test_subdirectories_are_excluded_by_default(self):
        (self.folder / "nested/deep").mkdir(parents=True)
        (self.folder / "root.txt").write_text("root")
        (self.folder / "nested/deep/child.txt").write_text("child")
        self.run_rules([{"id": "extension", "enabled": True}])
        self.assertTrue((self.folder / "txt/root.txt").is_file())
        self.assertEqual((self.folder / "nested/deep/child.txt").read_text(), "child")

    def test_recursive_extensions_and_repeat_run(self):
        (self.folder / "nested/日本語/deep").mkdir(parents=True)
        (self.folder / "nested/日本語/deep/é.TXT").write_text("nested")
        (self.folder / "root.txt").write_text("root")
        rules = [{"id": "extension", "enabled": True}]
        self.run_rules(rules, recursive=True)
        self.assertEqual((self.folder / "txt/é.TXT").read_text(), "nested")
        self.assertEqual((self.folder / "txt/root.txt").read_text(), "root")
        self.run_rules(rules, recursive=True)
        self.assertEqual(sorted(path.relative_to(self.folder).as_posix() for path in self.folder.rglob("*") if path.is_file()),
                         ["txt/root.txt", "txt/é.TXT"])

    def test_recursive_landscape_keeps_nonmatching_files_in_place(self):
        (self.folder / "nested").mkdir()
        self.media("nested/wide.png")
        self.media("nested/portrait.png", "40x80")
        (self.folder / "nested/note.txt").write_text("untouched")
        self.run_rules([{"id": "landscape", "enabled": True}], recursive=True)
        self.assertTrue((self.folder / "Landscape-FULL/wide.png").is_file())
        self.assertTrue((self.folder / "nested/portrait.png").is_file())
        self.assertEqual((self.folder / "nested/note.txt").read_text(), "untouched")

    def test_recursive_rule_order(self):
        (self.folder / "nested").mkdir()
        self.media("nested/first.png")
        rules = [{"id": "landscape", "enabled": True}, {"id": "extension", "enabled": True}]
        self.run_rules(rules, recursive=True)
        self.assertTrue((self.folder / "Landscape-FULL/png/first.png").is_file())
        self.media("nested/second.png")
        self.run_rules(list(reversed(rules)), recursive=True)
        self.assertTrue((self.folder / "png/Landscape-FULL/first.png").is_file())
        self.assertTrue((self.folder / "png/Landscape-FULL/second.png").is_file())

    def test_recursive_disabled_rules_do_not_flatten_files(self):
        (self.folder / "nested").mkdir()
        source = self.folder / "nested/note.txt"
        source.write_text("untouched")
        self.run_rules([{"id": "landscape", "enabled": False}, {"id": "extension", "enabled": False}], recursive=True)
        self.assertEqual(source.read_text(), "untouched")
        self.assertFalse((self.folder / "note.txt").exists())

    def test_recursive_duplicate_names_fail_without_overwrite(self):
        for name in ("a", "b"):
            (self.folder / name).mkdir()
            (self.folder / name / "note.txt").write_text(name)
        with self.assertRaises(FileExistsError):
            self.run_rules([{"id": "extension", "enabled": True}], recursive=True)
        self.assertEqual((self.folder / "txt/note.txt").read_text(), "a")
        self.assertEqual((self.folder / "b/note.txt").read_text(), "b")

    def test_media_shapes_and_other_files(self):
        self.media("wide.png")
        self.media("square.png", "40x40")
        self.media("portrait.png", "40x80")
        self.media("movie.mp4")
        (self.folder / "note.txt").write_text("text")
        self.run_rules([{"id": "landscape", "enabled": True}])
        for name in ("wide.png", "square.png", "movie.mp4"):
            self.assertTrue((self.folder / "Landscape-FULL" / name).is_file())
        self.assertTrue((self.folder / "portrait.png").is_file())
        self.assertTrue((self.folder / "note.txt").is_file())

    def test_rule_order_changes_nesting(self):
        self.media("first.png")
        rules = [{"id": "landscape", "enabled": True}, {"id": "extension", "enabled": True}]
        self.run_rules(rules)
        self.assertTrue((self.folder / "Landscape-FULL/png/first.png").is_file())
        self.media("second.png")
        self.run_rules(list(reversed(rules)))
        self.assertTrue((self.folder / "png/Landscape-FULL/second.png").is_file())

    def test_disabled_rules_and_existing_folders(self):
        self.media("landscape.PNG")
        (self.folder / "readme").write_text("text")
        (self.folder / "png").mkdir()
        (self.folder / "png/existing.txt").write_text("untouched")
        self.run_rules([{"id": "landscape", "enabled": False}, {"id": "extension", "enabled": True}])
        self.assertTrue((self.folder / "png/landscape.PNG").is_file())
        self.assertTrue((self.folder / "no-extension/readme").is_file())
        self.assertEqual((self.folder / "png/existing.txt").read_text(), "untouched")

    def test_collision_stops_without_overwrite(self):
        (self.folder / "txt").mkdir()
        (self.folder / "txt/note.txt").write_text("original")
        (self.folder / "note.txt").write_text("incoming")
        with self.assertRaises(FileExistsError):
            self.run_rules([{"id": "extension", "enabled": True}])
        self.assertEqual((self.folder / "txt/note.txt").read_text(), "original")
        self.assertEqual((self.folder / "note.txt").read_text(), "incoming")

    def test_corrupt_media_fails(self):
        (self.folder / "bad.png").write_bytes(b"invalid")
        with self.assertRaises(ZeroDivisionError):
            self.run_rules([{"id": "landscape", "enabled": True}])
        self.assertTrue((self.folder / "bad.png").is_file())

    def test_display_aspect_ratio_and_rotation(self):
        anamorphic = self.media("anamorphic.mp4", "40x80", "-vf", "setsar=4/1")
        self.assertTrue(is_landscape(anamorphic, FFPROBE))
        wide = self.media("wide.mp4")
        rotated = self.folder / "rotated.mp4"
        subprocess.run([str(FFMPEG), "-v", "error", "-display_rotation", "90", "-i", str(wide), "-c", "copy", str(rotated)], check=True)
        self.assertFalse(is_landscape(rotated, FFPROBE))

    def test_worker_handles_unicode_folder(self):
        folder = self.folder / "日本語 é"
        folder.mkdir()
        (folder / "é.txt").write_text("preserved")
        result = subprocess.run([sys.executable, str(ROOT / "main.py"), "--worker", str(folder),
                                 json.dumps([{"id": "extension", "enabled": True}]), "Landscape-FULL"],
                                check=True, capture_output=True, encoding="utf-8",
                                env=__import__("os").environ | {"PYTHONIOENCODING": "utf-8"})
        self.assertIn("Completed", result.stdout)
        self.assertEqual((folder / "txt/é.txt").read_text(), "preserved")
