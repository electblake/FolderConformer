import json
import os
import subprocess
import sys
from fractions import Fraction
from itertools import groupby
from pathlib import Path

from PySide6.QtCore import QMimeDatabase


class RunControl:
    def __init__(self):
        self.stopped = False

    def checkpoint(self):
        print("Control: ready", flush=True)
        self.stopped = sys.stdin.readline().strip() == "stop"
        return not self.stopped


def is_landscape(path: Path, ffprobe: Path) -> bool:
    result = subprocess.run(
        [str(ffprobe), "-v", "error", "-select_streams", "v:0",
         "-show_streams", "-of", "json", str(path)],
        check=True, stdout=subprocess.PIPE, text=True, encoding="utf-8",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    stream = json.loads(result.stdout)["streams"][0]
    ratio = Fraction(stream["width"], stream["height"])
    sar = stream.get("sample_aspect_ratio", "N/A")
    if sar not in ("N/A", "0:1"):
        ratio *= Fraction(sar.replace(":", "/"))
    for side_data in stream.get("side_data_list", []):
        if "rotation" in side_data and abs(side_data["rotation"]) % 180 == 90:
            ratio = 1 / ratio
    return ratio >= 1


def conform(folder: Path, rules: list[dict], landscape_folder: str, ffprobe: Path,
            video_folder: str, image_folder: str, video_extensions: str, image_extensions: str,
            recursive: bool = False, control=None):
    video_suffixes = {extension.strip().lstrip(".").lower() for extension in video_extensions.split(";") if extension.strip()}
    image_suffixes = {extension.strip().lstrip(".").lower() for extension in image_extensions.split(";") if extension.strip()}
    files_processed = files_moved = folders_renamed = folders_moved = 0
    enabled_rules = [rule for rule in rules if rule["enabled"]]
    for file_rules, group in groupby(enabled_rules, key=lambda rule: rule["id"] in ("landscape", "extension")):
        if file_rules:
            processed, moved = conform_files(folder, list(group), landscape_folder, ffprobe, recursive, control)
            files_processed += processed
            files_moved += moved
            if control is not None and control.stopped:
                break
            continue
        for rule in group:
            if control is not None and not control.checkpoint():
                break
            directories = [folder]
            if recursive:
                pending = [folder]
                while pending:
                    with os.scandir(pending.pop()) as entries:
                        for entry in entries:
                            if entry.is_dir(follow_symlinks=False):
                                child = Path(entry.path)
                                directories.append(child)
                                pending.append(child)
            moves = []
            for parent in reversed(directories):
                with os.scandir(parent) as entries:
                    children = sorted(Path(entry.path) for entry in entries if entry.is_dir(follow_symlinks=False))
                for source in children:
                    name = source.name.lower()
                    target = source
                    if rule["id"] == "rename_images" and name in ("image", "images"):
                        target = parent / image_folder
                    elif rule["id"] == "rename_videos" and name in ("video", "videos"):
                        target = parent / video_folder
                    elif rule["id"] == "photo_extensions" and name in image_suffixes:
                        if parent.name.lower() == Path(image_folder).name.lower():
                            continue
                        target = parent / image_folder / source.name
                    elif rule["id"] == "video_extensions" and name in video_suffixes:
                        if parent.name.lower() == Path(video_folder).name.lower():
                            continue
                        target = parent / video_folder / source.name
                    if str(target) != str(source):
                        moves.append((source, target))
            print(f"Folder rule {rule['id']}: {len(moves)} folders to change", flush=True)
            for index, (source, target) in enumerate(moves, 1):
                target.parent.mkdir(parents=True, exist_ok=True)
                source.rename(target)
                if rule["id"] in ("rename_images", "rename_videos"):
                    folders_renamed += 1
                    action = "Renamed folder"
                else:
                    folders_moved += 1
                    action = "Moved folder"
                print(f"[{index}/{len(moves)}] {action}: {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
        if control is not None and control.stopped:
            break
    print(f"Completed: {files_processed} files processed, {files_moved} files moved, "
          f"{folders_renamed} folders renamed, {folders_moved} folders moved.", flush=True)


def conform_files(folder: Path, rules: list[dict], landscape_folder: str, ffprobe: Path, recursive: bool = False,
                  control=None):
    files = []
    print(f"Scanning {folder}", flush=True)
    directories = [folder]
    checked = 0
    while directories:
        with os.scandir(directories.pop()) as entries:
            for entry in entries:
                checked += 1
                if entry.is_file():
                    files.append(Path(entry.path))
                elif recursive and entry.is_dir(follow_symlinks=False):
                    directories.append(Path(entry.path))
                if checked % 500 == 0:
                    print(f"Scanning: {checked} entries checked, {len(files)} files found", flush=True)
    files.sort()
    print(f"Found {len(files)} files", flush=True)
    moved = 0
    processed = 0
    mime_database = QMimeDatabase()
    for index, source in enumerate(files, 1):
        if control is not None and not control.checkpoint():
            break
        destination = folder
        for rule in rules:
            if not rule["enabled"]:
                continue
            if rule["id"] == "landscape":
                mime = mime_database.mimeTypeForFile(
                    str(source), QMimeDatabase.MatchMode.MatchExtension
                ).name()
                if mime.startswith(("video/", "image/")) and is_landscape(source, ffprobe):
                    destination /= landscape_folder
            elif rule["id"] == "extension":
                destination /= source.suffix.lstrip(".").lower() or "no-extension"
        target = destination / source.name if destination != folder else source
        if target != source:
            destination.mkdir(parents=True, exist_ok=True)
            source.rename(target)
            moved += 1
            print(f"{source.name} → {target.relative_to(folder)}", flush=True)
        print(f"[{index}/{len(files)}] {source.name}", flush=True)
        processed += 1
    return processed, moved
