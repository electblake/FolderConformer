import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication
from static_ffmpeg.run import get_platform_dir

from folderconformer.pipeline import RunControl, check_rule, conform, empty_directories, image_files, is_landscape, video_files


ROOT = Path(__file__).resolve().parent.parent
FFMPEG = Path(get_platform_dir()) / "ffmpeg.exe"
FFPROBE = Path(get_platform_dir()) / "ffprobe.exe"
APP = QApplication.instance() or QApplication([])
FOLDER_FILES = ("video/", "photo/",
                "mp4;ts;m4v;wmv;avi;mov;mkv;webm;mpg;mpeg;mts;m2ts;m2v;vob;flv;3gp;3g2;ogv;asf",
                "jpg;jpeg;png;webp;heic")


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

    def run_rules(self, rules, enumerate_conflicts=False):
        with contextlib.redirect_stdout(io.StringIO()):
            conform(self.folder, rules, "Landscape-FULL", FFPROBE, *FOLDER_FILES,
                    enumerate_conflicts=enumerate_conflicts)

    def test_summary_counts_folder_changes_when_no_files_are_scanned(self):
        for name in ("Images", "Videos", "jpg", "mp4"):
            (self.folder / name).mkdir()
        rules = [{"id": rule_id, "enabled": True} for rule_id in (
            "rename_images", "rename_videos", "photo_extensions", "video_extensions", "extension",
        )]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            conform(self.folder, rules, "Landscape-FULL", FFPROBE, *FOLDER_FILES)
        lines = output.getvalue().splitlines()
        self.assertIn("[1/1] Renamed folder: Images \u2192 photo", lines)
        self.assertIn("[1/1] Renamed folder: Videos \u2192 video", lines)
        self.assertTrue((self.folder / "jpg").is_dir())
        self.assertTrue((self.folder / "mp4").is_dir())
        self.assertEqual([line for line in lines if line.startswith("Completed:")], [
            "Completed: 0 files processed, 0 files moved, 2 folders renamed.",
        ])

    def test_video_rule_flattens_only_root_and_direct_extension_containers(self):
        for name in ("MP4/deep", "video/mkv/deep", "other", "video/other"):
            (self.folder / name).mkdir(parents=True)
        for name in ("root.MP4", "MP4/one.mp4", "video/mkv/two.mkv", "MP4/captions.srt",
                     "MP4/deep/keep.mp4", "video/mkv/deep/keep.mkv", "other/keep.mp4",
                     "video/other/keep.mp4", "video/done.mp4", "keep.txt"):
            (self.folder / name).write_text(name)
        rules = [{"id": "video_extensions", "enabled": True}]
        self.assertEqual(len(video_files(self.folder, "video/", " .MP4; mkv; ")), 4)
        self.run_rules(rules)
        for name in ("root.MP4", "one.mp4", "two.mkv", "captions.srt"):
            self.assertTrue((self.folder / "video" / name).is_file())
        for name in ("MP4/deep/keep.mp4", "video/mkv/deep/keep.mkv", "other/keep.mp4",
                     "video/other/keep.mp4", "keep.txt"):
            self.assertEqual((self.folder / name).read_text(), name)
        self.assertEqual(video_files(self.folder, "video/", FOLDER_FILES[2]), [])
        self.run_rules(rules)
        self.assertTrue((self.folder / "MP4").is_dir())

    def test_video_conflicts_remain_bad_until_resolved(self):
        for name in ("mp4", "video/mp4"):
            (self.folder / name).mkdir(parents=True)
        for name in ("same.mp4", "mp4/same.mp4", "video/mp4/same.mp4", "video/same.mp4"):
            (self.folder / name).write_text(name)
        rules = [{"id": "video_extensions", "enabled": True}]
        self.run_rules(rules)
        self.assertEqual(len(video_files(self.folder, "video/", "mp4")), 3)
        self.assertEqual((self.folder / "video/same.mp4").read_text(), "video/same.mp4")
        self.run_rules(rules, enumerate_conflicts=True)
        self.assertEqual(video_files(self.folder, "video/", "mp4"), [])
        self.assertEqual({path.read_text() for path in (self.folder / "video").glob("*.mp4")},
                         {"same.mp4", "mp4/same.mp4", "video/mp4/same.mp4", "video/same.mp4"})

    def test_image_rule_flattens_only_root_and_direct_extension_containers(self):
        for name in ("JPG/deep", "photo/png/deep", "other", "photo/other"):
            (self.folder / name).mkdir(parents=True)
        for name in ("root.JPG", "JPG/one.jpg", "photo/png/two.png", "JPG/captions.srt",
                     "JPG/deep/keep.jpg", "photo/png/deep/keep.png", "other/keep.jpg",
                     "photo/other/keep.jpg", "photo/done.jpg", "keep.txt"):
            (self.folder / name).write_text(name)
        rules = [{"id": "photo_extensions", "enabled": True}]
        self.assertEqual(len(image_files(self.folder, "photo/", " .JPG; png; ")), 4)
        self.run_rules(rules)
        for name in ("root.JPG", "one.jpg", "two.png", "captions.srt"):
            self.assertTrue((self.folder / "photo" / name).is_file())
        for name in ("JPG/deep/keep.jpg", "photo/png/deep/keep.png", "other/keep.jpg",
                     "photo/other/keep.jpg", "keep.txt"):
            self.assertEqual((self.folder / name).read_text(), name)
        self.assertEqual(image_files(self.folder, "photo/", FOLDER_FILES[3]), [])
        self.run_rules(rules)
        self.assertTrue((self.folder / "JPG").is_dir())

    def test_image_conflicts_remain_bad_until_resolved(self):
        for name in ("jpg", "photo/jpg"):
            (self.folder / name).mkdir(parents=True)
        for name in ("same.jpg", "jpg/same.jpg", "photo/jpg/same.jpg", "photo/same.jpg"):
            (self.folder / name).write_text(name)
        rules = [{"id": "photo_extensions", "enabled": True}]
        self.run_rules(rules)
        self.assertEqual(len(image_files(self.folder, "photo/", "jpg")), 3)
        self.assertEqual((self.folder / "photo/same.jpg").read_text(), "photo/same.jpg")
        self.run_rules(rules, enumerate_conflicts=True)
        self.assertEqual(image_files(self.folder, "photo/", "jpg"), [])
        self.assertEqual({path.read_text() for path in (self.folder / "photo").glob("*.jpg")},
                         {"same.jpg", "jpg/same.jpg", "photo/jpg/same.jpg", "photo/same.jpg"})

    def test_empty_directory_rule_removes_nested_empty_trees_only(self):
        (self.folder / "empty/deep/leaf").mkdir(parents=True)
        (self.folder / "kept/empty").mkdir(parents=True)
        (self.folder / "kept/data.txt").write_text("keep")
        self.assertTrue(list(empty_directories(self.folder)))
        self.run_rules([{"id": "remove_empty_dirs", "enabled": True}])
        self.assertEqual(list(empty_directories(self.folder)), [])
        self.assertFalse((self.folder / "empty").exists())
        self.assertFalse((self.folder / "kept/empty").exists())
        self.assertEqual((self.folder / "kept/data.txt").read_text(), "keep")
        self.assertTrue(self.folder.is_dir())

    def test_summary_counts_file_moves_and_folder_moves(self):
        (self.folder / "picture.jpg").write_text("picture")
        (self.folder / "note.txt").write_text("note")
        rules = [{"id": "extension", "enabled": True}, {"id": "photo_extensions", "enabled": True}]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            conform(self.folder, rules, "Landscape-FULL", FFPROBE, *FOLDER_FILES)
        self.assertEqual(output.getvalue().splitlines()[-1],
                         "Completed: 3 files processed, 3 files moved, 0 folders renamed.")

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
        self.run_rules(rules)
        for destination, names in (("", photos), ("", videos), ("", ("gif", "txt"))):
            for name in names:
                self.assertEqual((self.folder / destination / name / "nested/keep.txt").read_text(), name)
        self.assertEqual((self.folder / "jpg.txt").read_text(), "file")

    def test_folder_rules_follow_file_rule_order(self):
        (self.folder / "first.JPG").write_text("first")
        rules = [{"id": "extension", "enabled": True}, {"id": "photo_extensions", "enabled": True}]
        self.run_rules(rules)
        self.assertEqual((self.folder / "photo/first.JPG").read_text(), "first")
        (self.folder / "second.PNG").write_text("second")
        self.run_rules(list(reversed(rules)))
        self.assertEqual((self.folder / "photo/second.PNG").read_text(), "second")

    def test_configured_folders_and_extensions_replace_defaults(self):
        for name in ("Images", "Videos", "GIF", "mxf", "jpg", "mp4"):
            (self.folder / name).mkdir()
            (self.folder / name / "keep.txt").write_text(name)
        rules = [{"id": rule_id, "enabled": True} for rule_id in (
            "rename_images", "rename_videos", "photo_extensions", "video_extensions",
        )]
        with contextlib.redirect_stdout(io.StringIO()):
            conform(self.folder, rules, "Wide", FFPROBE, "Clips/", "Pictures/", " .MXF; ", " GIF; ")
            conform(self.folder, rules, "Wide", FFPROBE, "Clips/", "Pictures/", " .MXF; ", " GIF; ")
        for path, content in (("Pictures/keep.txt", "Images"), ("Clips/keep.txt", "Videos"),
                              ("GIF/keep.txt", "GIF"), ("mxf/keep.txt", "mxf"),
                              ("jpg/keep.txt", "jpg"), ("mp4/keep.txt", "mp4")):
            self.assertEqual((self.folder / path).read_text(), content)

    def test_folder_rules_ignore_nested_folders_and_disabled_rules(self):
        (self.folder / "nested/IMAGES/PNG").mkdir(parents=True)
        (self.folder / "nested/IMAGES/PNG/item.txt").write_text("content")
        rules = [{"id": "rename_images", "enabled": True}, {"id": "photo_extensions", "enabled": True}]
        self.run_rules(rules)
        self.assertTrue((self.folder / "nested/IMAGES/PNG/item.txt").is_file())
        self.run_rules([{"id": rule["id"], "enabled": False} for rule in rules])
        self.assertTrue((self.folder / "nested/IMAGES/PNG/item.txt").is_file())
        self.run_rules(rules)
        self.assertEqual((self.folder / "nested/IMAGES/PNG/item.txt").read_text(), "content")

    def test_existing_destination_merges_source_contents(self):
        (self.folder / "images").mkdir()
        (self.folder / "images/incoming.txt").write_text("incoming")
        (self.folder / "photo").mkdir()
        (self.folder / "photo/existing.txt").write_text("existing")
        self.run_rules([{"id": "rename_images", "enabled": True}])
        self.assertFalse((self.folder / "images").exists())
        self.assertEqual((self.folder / "photo/incoming.txt").read_text(), "incoming")
        self.assertEqual((self.folder / "photo/existing.txt").read_text(), "existing")

    def test_single_media_folders_create_merge_and_preserve_conflicts(self):
        for rule_id, aliases, destination in (("rename_images", ("image", "IMAGES"), "Pictures"),
                                             ("rename_videos", ("video", "VIDEOS"), "Clips")):
            with self.subTest(rule=rule_id):
                root = self.folder / rule_id
                root.mkdir()
                rules = [{"id": rule_id, "enabled": True}]
                config = ("Clips/", "Pictures/", "mp4", "png")
                self.assertEqual(check_rule(root, rule_id, *config, FFPROBE), "BAD")
                with contextlib.redirect_stdout(io.StringIO()):
                    conform(root, rules, "Wide", FFPROBE, *config)
                target = root / destination
                self.assertTrue(target.is_dir())
                self.assertEqual(check_rule(root, rule_id, *config, FFPROBE), "OK")
                (target / "shared").mkdir()
                (target / "shared/same.txt").write_text("existing")
                for alias in aliases:
                    (root / alias / "shared").mkdir(parents=True)
                    (root / alias / "shared/same.txt").write_text(alias)
                    (root / alias / f"{alias}.txt").write_text(alias)
                (root / "unrelated" / aliases[0]).mkdir(parents=True)
                with contextlib.redirect_stdout(io.StringIO()):
                    conform(root, rules, "Wide", FFPROBE, *config)
                self.assertEqual(check_rule(root, rule_id, *config, FFPROBE), "BAD")
                self.assertEqual((target / "shared/same.txt").read_text(), "existing")
                for alias in aliases:
                    self.assertEqual((target / f"{alias}.txt").read_text(), alias)
                    self.assertEqual((root / alias / "shared/same.txt").read_text(), alias)
                with contextlib.redirect_stdout(io.StringIO()):
                    conform(root, rules, "Wide", FFPROBE, *config, enumerate_conflicts=True)
                self.assertEqual(check_rule(root, rule_id, *config, FFPROBE), "OK")
                self.assertEqual({path.read_text() for path in (target / "shared").iterdir()},
                                 {"existing", *aliases})
                for alias in aliases:
                    self.assertFalse((root / alias).exists())
                self.assertTrue((root / "unrelated" / aliases[0]).is_dir())
                with contextlib.redirect_stdout(io.StringIO()):
                    conform(root, rules, "Wide", FFPROBE, *config, enumerate_conflicts=True)
                self.assertEqual(len(list((target / "shared").iterdir())), 3)

    def test_single_media_folders_merge_both_aliases_into_missing_destination(self):
        for rule_id, aliases, destination in (("rename_images", ("image", "images"), "photo"),
                                             ("rename_videos", ("video", "videos"), "clips")):
            with self.subTest(rule=rule_id):
                root = self.folder / rule_id
                for alias in aliases:
                    (root / alias / "nested").mkdir(parents=True)
                    (root / alias / "nested" / f"{alias}.txt").write_text(alias)
                with contextlib.redirect_stdout(io.StringIO()):
                    conform(root, [{"id": rule_id, "enabled": True}], "Wide", FFPROBE,
                            "clips", "photo", "mp4", "png")
                for alias in aliases:
                    self.assertFalse((root / alias).exists())
                    self.assertEqual((root / destination / "nested" / f"{alias}.txt").read_text(), alias)
                self.assertEqual(check_rule(root, rule_id, "clips", "photo", "mp4", "png", FFPROBE), "OK")

    def test_case_only_destination_rename_with_another_alias_to_merge(self):
        for rule_id, aliases, destination in (("rename_images", ("image", "images"), "IMAGES"),
                                             ("rename_videos", ("video", "videos"), "VIDEOS")):
            with self.subTest(rule=rule_id):
                root = self.folder / rule_id
                for alias in aliases:
                    (root / alias).mkdir(parents=True)
                    (root / alias / f"{alias}.txt").write_text(alias)
                config = ("VIDEOS", "IMAGES", "mp4", "png")
                self.assertEqual(check_rule(root, rule_id, *config, FFPROBE), "BAD")
                with contextlib.redirect_stdout(io.StringIO()):
                    conform(root, [{"id": rule_id, "enabled": True}], "Wide", FFPROBE, *config)
                self.assertEqual([path.name for path in root.iterdir()], [destination])
                self.assertEqual({path.read_text() for path in (root / destination).iterdir()}, set(aliases))
                self.assertEqual(check_rule(root, rule_id, *config, FFPROBE), "OK")

    def test_merge_file_directory_conflicts_skip_or_enumerate_without_loss(self):
        (self.folder / "images/folder.txt").mkdir(parents=True)
        (self.folder / "images/folder.txt/child.txt").write_text("nested source")
        (self.folder / "images/file.txt").write_text("source")
        (self.folder / "photo/file.txt").mkdir(parents=True)
        (self.folder / "photo/file.txt/child.txt").write_text("nested destination")
        (self.folder / "photo/folder.txt").write_text("destination")
        rules = [{"id": "rename_images", "enabled": True}]
        self.run_rules(rules)
        self.assertEqual(check_rule(self.folder, "rename_images", *FOLDER_FILES, FFPROBE), "BAD")
        self.assertEqual((self.folder / "images/folder.txt/child.txt").read_text(), "nested source")
        self.assertEqual((self.folder / "images/file.txt").read_text(), "source")
        self.run_rules(rules, enumerate_conflicts=True)
        self.assertEqual((self.folder / "photo/folder.txt_1/child.txt").read_text(), "nested source")
        self.assertEqual((self.folder / "photo/file_1.txt").read_text(), "source")
        self.assertEqual((self.folder / "photo/file.txt/child.txt").read_text(), "nested destination")
        self.assertEqual((self.folder / "photo/folder.txt").read_text(), "destination")
        self.assertEqual(check_rule(self.folder, "rename_images", *FOLDER_FILES, FFPROBE), "OK")

    def test_merge_stops_without_removing_unmoved_source_contents(self):
        (self.folder / "images").mkdir()
        (self.folder / "photo").mkdir()
        (self.folder / "images/a.txt").write_text("a")
        (self.folder / "images/b.txt").write_text("b")
        control = RunControl()
        with patch("sys.stdin", io.StringIO("continue\ncontinue\nstop\n")), contextlib.redirect_stdout(io.StringIO()):
            conform(self.folder, [{"id": "rename_images", "enabled": True}], "Wide", FFPROBE,
                    *FOLDER_FILES, control=control)
        self.assertTrue(control.stopped)
        self.assertEqual((self.folder / "photo/a.txt").read_text(), "a")
        self.assertEqual((self.folder / "images/b.txt").read_text(), "b")

    def test_extension_only_processes_input_root(self):
        (self.folder / "nested/deep").mkdir(parents=True)
        (self.folder / "root.txt").write_text("root")
        (self.folder / "nested/deep/child.txt").write_text("child")
        self.run_rules([{"id": "extension", "enabled": True}])
        self.assertTrue((self.folder / "txt/root.txt").is_file())
        self.assertEqual((self.folder / "nested/deep/child.txt").read_text(), "child")

    def test_root_extensions_and_repeat_run_preserve_nested_files(self):
        (self.folder / "nested/日本語/deep").mkdir(parents=True)
        (self.folder / "nested/日本語/deep/é.TXT").write_text("nested")
        (self.folder / "root.txt").write_text("root")
        rules = [{"id": "extension", "enabled": True}]
        self.run_rules(rules)
        self.assertEqual((self.folder / "nested/日本語/deep/é.TXT").read_text(), "nested")
        self.assertEqual((self.folder / "txt/root.txt").read_text(), "root")
        self.run_rules(rules)
        self.assertEqual(sorted(path.relative_to(self.folder).as_posix() for path in self.folder.rglob("*") if path.is_file()),
                         ["nested/日本語/deep/é.TXT", "txt/root.txt"])

    def test_landscape_rules_use_only_configured_media_folder_direct_files(self):
        for rule_id, directory, suffix, other_suffix in (("landscape", "Clips", "mp4", "png"),
                                                       ("landscape_images", "Pictures", "png", "mp4")):
            with self.subTest(rule=rule_id):
                (self.folder / directory / "nested").mkdir(parents=True)
                for name, size in (("wide", "80x40"), ("square", "40x40"), ("portrait", "40x80")):
                    self.media(f"{directory}/{name}.{suffix}", size)
                self.media(f"{directory}/nested/deep.{suffix}")
                self.media(f"root.{suffix}")
                (self.folder / directory / f"other.{other_suffix}").write_text("not matching media")
                with contextlib.redirect_stdout(io.StringIO()):
                    conform(self.folder, [{"id": rule_id, "enabled": True}], "Wide", FFPROBE,
                            "Clips/", "Pictures/", " .MP4; ", " .PNG; ")
                for name in ("wide", "square"):
                    self.assertTrue((self.folder / directory / "Wide" / f"{name}.{suffix}").is_file())
                for name in (f"portrait.{suffix}", f"nested/deep.{suffix}", f"other.{other_suffix}"):
                    self.assertTrue((self.folder / directory / name).is_file())
                self.assertTrue((self.folder / f"root.{suffix}").is_file())

    def test_landscape_rules_respect_conflict_settings_and_repeat_run(self):
        for rule_id, directory, suffix in (("landscape", "video", "mp4"), ("landscape_images", "photo", "png")):
            with self.subTest(rule=rule_id):
                (self.folder / directory / "Landscape-FULL").mkdir(parents=True)
                self.media(f"{directory}/wide.{suffix}")
                target = self.folder / directory / "Landscape-FULL" / f"wide.{suffix}"
                target.write_bytes(b"existing")
                rules = [{"id": rule_id, "enabled": True}]
                self.run_rules(rules)
                self.assertTrue((self.folder / directory / f"wide.{suffix}").is_file())
                self.assertEqual(target.read_bytes(), b"existing")
                self.run_rules(rules, enumerate_conflicts=True)
                self.assertTrue((target.parent / f"wide_1.{suffix}").is_file())
                self.run_rules(rules, enumerate_conflicts=True)
                self.assertFalse((target.parent / f"wide_2.{suffix}").exists())

    def test_disabled_rules_do_not_flatten_files(self):
        (self.folder / "nested").mkdir()
        source = self.folder / "nested/note.txt"
        source.write_text("untouched")
        self.run_rules([{"id": "landscape", "enabled": False}, {"id": "extension", "enabled": False}])
        self.assertEqual(source.read_text(), "untouched")
        self.assertFalse((self.folder / "note.txt").exists())

    def test_extension_ignores_duplicate_names_in_subdirectories(self):
        for name in ("a", "b"):
            (self.folder / name).mkdir()
            (self.folder / name / "note.txt").write_text(name)
        self.run_rules([{"id": "extension", "enabled": True}])
        self.assertEqual((self.folder / "a/note.txt").read_text(), "a")
        self.assertFalse((self.folder / "txt").exists())
        self.assertEqual((self.folder / "b/note.txt").read_text(), "b")

    def test_landscape_and_extension_have_independent_scopes_in_either_order(self):
        (self.folder / "video").mkdir()
        (self.folder / "photo").mkdir()
        rules = [{"id": name, "enabled": True} for name in ("landscape", "landscape_images", "extension")]
        self.media("video/first.mp4")
        self.media("photo/first.png")
        (self.folder / "first.txt").write_text("first")
        self.run_rules(rules)
        self.media("video/second.mp4")
        self.media("photo/second.png")
        (self.folder / "second.txt").write_text("second")
        self.run_rules(list(reversed(rules)))
        for name in ("first", "second"):
            self.assertTrue((self.folder / f"video/Landscape-FULL/{name}.mp4").is_file())
            self.assertTrue((self.folder / f"photo/Landscape-FULL/{name}.png").is_file())
            self.assertEqual((self.folder / f"txt/{name}.txt").read_text(), name)

    def test_disabled_rules_and_existing_folders(self):
        self.media("landscape.PNG")
        (self.folder / "readme").write_text("text")
        (self.folder / "png").mkdir()
        (self.folder / "png/existing.txt").write_text("untouched")
        self.run_rules([{"id": "landscape", "enabled": False}, {"id": "extension", "enabled": True}])
        self.assertTrue((self.folder / "png/landscape.PNG").is_file())
        self.assertTrue((self.folder / "no-extension/readme").is_file())
        self.assertEqual((self.folder / "png/existing.txt").read_text(), "untouched")

    def test_collision_skips_without_overwrite_and_continues(self):
        (self.folder / "txt").mkdir()
        (self.folder / "txt/note.txt").write_text("original")
        (self.folder / "note.txt").write_text("incoming")
        (self.folder / "other.txt").write_text("other")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            conform(self.folder, [{"id": "extension", "enabled": True}], "Wide", FFPROBE, *FOLDER_FILES)
        self.assertEqual((self.folder / "txt/note.txt").read_text(), "original")
        self.assertEqual((self.folder / "note.txt").read_text(), "incoming")
        self.assertEqual((self.folder / "txt/other.txt").read_text(), "other")
        self.assertIn("Skipped name conflict: note.txt", output.getvalue())
        self.assertIn("Completed: 2 files processed, 1 files moved", output.getvalue())

    def test_conflicts_enumerate_preserving_suffix_and_existing_destinations(self):
        for name, destination in (("note.TXT", "txt"), ("日本語", "no-extension"), ("archive.tar.gz", "gz")):
            with self.subTest(name=name):
                target = self.folder / destination
                target.mkdir()
                (target / name).write_text("original")
                source = self.folder / name
                source.write_text("incoming")
                (target / f"{source.stem}_1{source.suffix}").write_text("occupied")
                (target / f"{source.stem}_2{source.suffix}").mkdir()
                self.run_rules([{"id": "extension", "enabled": True}], enumerate_conflicts=True)
                self.assertEqual((target / name).read_text(), "original")
                self.assertEqual((target / f"{source.stem}_1{source.suffix}").read_text(), "occupied")
                self.assertTrue((target / f"{source.stem}_2{source.suffix}").is_dir())
                self.assertEqual((target / f"{source.stem}_3{source.suffix}").read_text(), "incoming")
                self.assertFalse(source.exists())

    def test_extension_conflict_resolution_does_not_scan_nested_files(self):
        for name in ("a", "b", "c"):
            (self.folder / name).mkdir()
            (self.folder / name / "note.txt").write_text(name)
        rules = [{"id": "extension", "enabled": True}]
        self.run_rules(rules, enumerate_conflicts=True)
        self.run_rules(rules, enumerate_conflicts=True)
        self.assertFalse((self.folder / "txt").exists())
        for name in ("a", "b", "c"):
            self.assertEqual((self.folder / name / "note.txt").read_text(), name)

    def test_corrupt_media_fails(self):
        (self.folder / "photo").mkdir()
        (self.folder / "photo/bad.png").write_bytes(b"invalid")
        with self.assertRaises(ZeroDivisionError):
            self.run_rules([{"id": "landscape_images", "enabled": True}])
        self.assertTrue((self.folder / "photo/bad.png").is_file())

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
                                 json.dumps([{"id": "extension", "enabled": True}]), "Landscape-FULL", *FOLDER_FILES],
                                check=True, capture_output=True, encoding="utf-8",
                                env=__import__("os").environ | {"PYTHONIOENCODING": "utf-8"})
        self.assertIn("Completed", result.stdout)
        self.assertEqual((folder / "txt/é.txt").read_text(), "preserved")

    def test_worker_conflict_option_skips_or_enumerates(self):
        for enumerate_conflicts in (False, True):
            with self.subTest(enumerate_conflicts=enumerate_conflicts):
                folder = self.folder / str(enumerate_conflicts)
                (folder / "txt").mkdir(parents=True)
                (folder / "txt/note.txt").write_text("original")
                (folder / "note.txt").write_text("incoming")
                arguments = [sys.executable, str(ROOT / "main.py"), "--worker", str(folder),
                             json.dumps([{"id": "extension", "enabled": True}]), "Wide", *FOLDER_FILES]
                if enumerate_conflicts:
                    arguments.append("--enumerate-conflicts")
                result = subprocess.run(arguments, check=True, capture_output=True, encoding="utf-8")
                self.assertIn("Completed", result.stdout)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual((folder / "txt/note.txt").read_text(), "original")
                incoming = folder / "txt/note_1.txt" if enumerate_conflicts else folder / "note.txt"
                self.assertEqual(incoming.read_text(), "incoming")

    def test_stop_after_file_rules_preserves_later_files(self):
        (self.folder / "a.txt").write_text("a")
        (self.folder / "b.txt").write_text("b")
        control = RunControl()
        with patch("sys.stdin", io.StringIO("continue\nstop\n")), contextlib.redirect_stdout(io.StringIO()):
            conform(self.folder, [{"id": "extension", "enabled": True}], "Wide", FFPROBE,
                    *FOLDER_FILES, control=control)
        self.assertTrue(control.stopped)
        self.assertTrue((self.folder / "txt/a.txt").is_file())
        self.assertTrue((self.folder / "b.txt").is_file())

    def test_stop_between_folder_rules(self):
        (self.folder / "Images").mkdir()
        (self.folder / "Videos").mkdir()
        control = RunControl()
        rules = [{"id": name, "enabled": True} for name in ("rename_images", "rename_videos")]
        with patch("sys.stdin", io.StringIO("continue\nstop\n")), contextlib.redirect_stdout(io.StringIO()):
            conform(self.folder, rules, "Wide", FFPROBE, *FOLDER_FILES, control=control)
        self.assertTrue(control.stopped)
        self.assertTrue((self.folder / "photo").is_dir())
        self.assertTrue((self.folder / "Videos").is_dir())
