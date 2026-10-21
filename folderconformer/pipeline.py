import json
import os
import subprocess
import sys
from fractions import Fraction
from itertools import groupby
from pathlib import Path

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


def video_files(folder: Path, video_folder: str, video_extensions: str):
    suffixes = {value.strip().lstrip(".").lower() for value in video_extensions.split(";") if value.strip()}
    destination = folder / video_folder
    files = []
    containers = []
    with os.scandir(folder) as entries:
        for entry in entries:
            path = Path(entry.path)
            if entry.is_file() and path.suffix.lstrip(".").lower() in suffixes:
                files.append(path)
            elif entry.is_dir(follow_symlinks=False) and path != destination and entry.name.lower() in suffixes:
                containers.append(path)
            if entry.is_dir(follow_symlinks=False) and path == destination:
                with os.scandir(path) as children:
                    containers.extend(Path(child.path) for child in children
                                      if child.is_dir(follow_symlinks=False) and child.name.lower() in suffixes)
    for container in containers:
        with os.scandir(container) as entries:
            files.extend(Path(entry.path) for entry in entries if entry.is_file())
    return sorted(files)


def image_files(folder: Path, image_folder: str, image_extensions: str):
    suffixes = {value.strip().lstrip(".").lower() for value in image_extensions.split(";") if value.strip()}
    destination = folder / image_folder
    files = []
    containers = []
    with os.scandir(folder) as entries:
        for entry in entries:
            path = Path(entry.path)
            if entry.is_file() and path.suffix.lstrip(".").lower() in suffixes:
                files.append(path)
            elif entry.is_dir(follow_symlinks=False) and path != destination and entry.name.lower() in suffixes:
                containers.append(path)
            if entry.is_dir(follow_symlinks=False) and path == destination:
                with os.scandir(path) as children:
                    containers.extend(Path(child.path) for child in children
                                      if child.is_dir(follow_symlinks=False) and child.name.lower() in suffixes)
    for container in containers:
        with os.scandir(container) as entries:
            files.extend(Path(entry.path) for entry in entries if entry.is_file())
    return sorted(files)


def empty_directories(folder: Path):
    directories = []
    pending = [folder]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    child = Path(entry.path)
                    directories.append(child)
                    pending.append(child)
    for directory in reversed(directories):
        if not any(directory.iterdir()):
            yield directory


def check_rule(folder: Path, rule_id: str, video_folder: str, image_folder: str,
               video_extensions: str, image_extensions: str, ffprobe: Path):
    if rule_id == "extension":
        bad = any(path.is_file() for path in Path(folder).iterdir())
    elif rule_id in ("rename_images", "rename_videos"):
        names = ("image", "images") if rule_id == "rename_images" else ("video", "videos")
        destination = image_folder if rule_id == "rename_images" else video_folder
        target = Path(folder) / destination
        with os.scandir(folder) as entries:
            bad = not target.is_dir() or any(entry.is_dir(follow_symlinks=False) and entry.name.lower() in names
                                             and str(Path(entry.path)) != str(target) for entry in entries)
    elif rule_id == "video_extensions":
        bad = bool(video_files(Path(folder), video_folder, video_extensions))
    elif rule_id == "photo_extensions":
        bad = bool(image_files(Path(folder), image_folder, image_extensions))
    elif rule_id == "remove_empty_dirs":
        bad = any(empty_directories(Path(folder)))
    elif rule_id in ("landscape", "landscape_images"):
        directory = video_folder if rule_id == "landscape" else image_folder
        extensions = video_extensions if rule_id == "landscape" else image_extensions
        suffixes = {value.strip().lstrip(".").lower() for value in extensions.split(";") if value.strip()}
        target = Path(folder) / directory
        with os.scandir(folder):
            bad = not target.exists() or any(path.is_file() and path.suffix.lstrip(".").lower() in suffixes
                                             and is_landscape(path, ffprobe) for path in target.iterdir())
    return "BAD" if bad else "OK"


def merge_folder(source: Path, target: Path, root: Path, enumerate_conflicts: bool, control):
    target.mkdir(parents=True, exist_ok=True)
    processed = moved = 0
    with os.scandir(source) as entries:
        children = sorted((Path(entry.path), entry.is_dir(follow_symlinks=False)) for entry in entries)
    for child, is_directory in children:
        if control is not None and not control.checkpoint():
            return processed, moved
        destination = target / child.name
        if is_directory and destination.is_dir():
            child_processed, child_moved = merge_folder(child, destination, root, enumerate_conflicts, control)
            processed += child_processed
            moved += child_moved
            if control is not None and control.stopped:
                return processed, moved
            continue
        if not is_directory:
            processed += 1
        if os.path.lexists(destination) and not enumerate_conflicts:
            print(f"Skipped name conflict: {child.relative_to(root)} → {destination.relative_to(root)}", flush=True)
            continue
        number = 1
        while os.path.lexists(destination):
            name = f"{child.name}_{number}" if is_directory else f"{child.stem}_{number}{child.suffix}"
            destination = target / name
            number += 1
        child.rename(destination)
        if not is_directory:
            moved += 1
        print(f"Moved: {child.relative_to(root)} → {destination.relative_to(root)}", flush=True)
    if not any(source.iterdir()):
        source.rmdir()
    return processed, moved


def conform(folder: Path, rules: list[dict], landscape_folder: str, ffprobe: Path,
            video_folder: str, image_folder: str, video_extensions: str, image_extensions: str,
            control=None, enumerate_conflicts: bool = False):
    files_processed = files_moved = folders_renamed = 0
    enabled_rules = [rule for rule in rules if rule["enabled"]]
    for rule_id, group in groupby(enabled_rules, key=lambda rule: rule["id"]):
        if rule_id in ("landscape", "landscape_images", "extension"):
            source_folder = {"landscape": folder / video_folder,
                             "landscape_images": folder / image_folder, "extension": folder}[rule_id]
            extensions = image_extensions if rule_id == "landscape_images" else video_extensions
            processed, moved = conform_files(source_folder, list(group), landscape_folder, ffprobe, extensions,
                                            control, enumerate_conflicts)
            files_processed += processed
            files_moved += moved
            if control is not None and control.stopped:
                break
            continue
        for rule in group:
            if control is not None and not control.checkpoint():
                break
            if rule["id"] == "video_extensions":
                files = video_files(folder, video_folder, video_extensions)
                destination = folder / video_folder
                for index, source in enumerate(files, 1):
                    if control is not None and not control.checkpoint():
                        break
                    target = destination / source.name
                    if os.path.lexists(target) and not enumerate_conflicts:
                        print(f"Skipped name conflict: {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
                    else:
                        number = 1
                        while os.path.lexists(target):
                            target = destination / f"{source.stem}_{number}{source.suffix}"
                            number += 1
                        destination.mkdir(parents=True, exist_ok=True)
                        source.rename(target)
                        files_moved += 1
                        print(f"{source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
                    files_processed += 1
                    print(f"[{index}/{len(files)}] {source.name}", flush=True)
                if control is not None and control.stopped:
                    break
                continue
            if rule["id"] == "photo_extensions":
                files = image_files(folder, image_folder, image_extensions)
                destination = folder / image_folder
                for index, source in enumerate(files, 1):
                    if control is not None and not control.checkpoint():
                        break
                    target = destination / source.name
                    if os.path.lexists(target) and not enumerate_conflicts:
                        print(f"Skipped name conflict: {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
                    else:
                        number = 1
                        while os.path.lexists(target):
                            target = destination / f"{source.stem}_{number}{source.suffix}"
                            number += 1
                        destination.mkdir(parents=True, exist_ok=True)
                        source.rename(target)
                        files_moved += 1
                        print(f"{source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
                    files_processed += 1
                    print(f"[{index}/{len(files)}] {source.name}", flush=True)
                if control is not None and control.stopped:
                    break
                continue
            if rule["id"] == "remove_empty_dirs":
                removed = 0
                for directory in empty_directories(folder):
                    if control is not None and not control.checkpoint():
                        break
                    directory.rmdir()
                    removed += 1
                    print(f"Removed empty folder: {directory.relative_to(folder)}", flush=True)
                print(f"Removed {removed} empty folders.", flush=True)
                if control is not None and control.stopped:
                    break
                continue
            names = ("image", "images") if rule["id"] == "rename_images" else ("video", "videos")
            target = folder / (image_folder if rule["id"] == "rename_images" else video_folder)
            with os.scandir(folder) as entries:
                sources = sorted(Path(entry.path) for entry in entries
                                 if entry.is_dir(follow_symlinks=False) and entry.name.lower() in names
                                 and str(Path(entry.path)) != str(target))
            for index, source in enumerate(sources, 1):
                if not os.path.lexists(target) or source == target:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source.rename(target)
                    folders_renamed += 1
                    print(f"[{index}/{len(sources)}] Renamed folder: {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
                else:
                    processed, moved = merge_folder(source, target, folder, enumerate_conflicts, control)
                    files_processed += processed
                    files_moved += moved
                    if control is not None and control.stopped:
                        break
                    print(f"[{index}/{len(sources)}] Merged folder: {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
            target.mkdir(parents=True, exist_ok=True)
        if control is not None and control.stopped:
            break
    print(f"Completed: {files_processed} files processed, {files_moved} files moved, "
          f"{folders_renamed} folders renamed.", flush=True)


def conform_files(folder: Path, rules: list[dict], landscape_folder: str, ffprobe: Path, extensions: str, control=None, enumerate_conflicts: bool = False):
    suffixes = {value.strip().lstrip(".").lower() for value in extensions.split(";") if value.strip()}
    files = []
    print(f"Scanning {folder}", flush=True)
    with os.scandir(folder) as entries:
        for checked, entry in enumerate(entries, 1):
            if entry.is_file():
                files.append(Path(entry.path))
            if checked % 500 == 0:
                print(f"Scanning: {checked} entries checked, {len(files)} files found", flush=True)
    files.sort()
    print(f"Found {len(files)} files", flush=True)
    moved = 0
    processed = 0
    for index, source in enumerate(files, 1):
        if control is not None and not control.checkpoint():
            break
        destination = folder
        for rule in rules:
            if not rule["enabled"]:
                continue
            if rule["id"] in ("landscape", "landscape_images"):
                if source.suffix.lstrip(".").lower() in suffixes and is_landscape(source, ffprobe):
                    destination /= landscape_folder
            elif rule["id"] == "extension":
                destination /= source.suffix.lstrip(".").lower() or "no-extension"
        target = destination / source.name if destination != folder else source
        if target != source:
            if os.path.lexists(target) and not enumerate_conflicts:
                print(f"Skipped name conflict: {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
            else:
                number = 1
                while os.path.lexists(target):
                    target = destination / f"{source.stem}_{number}{source.suffix}"
                    number += 1
                destination.mkdir(parents=True, exist_ok=True)
                source.rename(target)
                moved += 1
                print(f"{source.name} → {target.relative_to(folder)}", flush=True)
        print(f"[{index}/{len(files)}] {source.name}", flush=True)
        processed += 1
    return processed, moved
