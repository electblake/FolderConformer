import json
import os
import subprocess
import sys
from fractions import Fraction
from itertools import groupby
from pathlib import Path
from threading import Lock

from folderconformer.music_model import DEFAULT_AUDIO_CLASSES
from folderconformer.workers import DEFAULT_WORKER_THREADS, RULE_IDENTIFIERS, MusicAnalysis, report, worker_results

class RunControl:
    def __init__(self):
        self.stopped = False
        self.lock = Lock()

    def checkpoint(self):
        with self.lock:
            if self.stopped:
                return False
            report("Control: ready", flush=True)
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


def data_files(folder: Path, data_folder: str, data_extensions: str):
    suffixes = {value.strip().lstrip(".").lower() for value in data_extensions.split(";") if value.strip()}
    destination = folder / data_folder
    files = []
    containers = []
    with os.scandir(folder) as entries:
        for entry in entries:
            path = Path(entry.path)
            if entry.is_file() and path.parent != destination and path.suffix.lstrip(".").lower() in suffixes:
                files.append(path)
            elif entry.is_dir(follow_symlinks=False) and path != destination and entry.name.lower() in suffixes:
                containers.append(path)
            if entry.is_dir(follow_symlinks=False) and path == destination:
                with os.scandir(path) as children:
                    containers.extend(Path(child.path) for child in children
                                      if child.is_dir(follow_symlinks=False) and child.name.lower() in suffixes)
    for container in containers:
        with os.scandir(container) as entries:
            files.extend(Path(entry.path) for entry in entries
                         if entry.is_file() and Path(entry.name).suffix.lstrip(".").lower() in suffixes)
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
               video_extensions: str, image_extensions: str, data_folder: str, data_extensions: str, ffprobe: Path,
               landscape_folder: str, music_folder="with-music", audio_classes=DEFAULT_AUDIO_CLASSES,
               empty_file_name=".forceGallery", music_threads=1):
    if rule_id == "create_empty_file":
        return "OK" if (folder / empty_file_name).is_file() else "BAD"
    if rule_id == "extension":
        with os.scandir(folder) as entries:
            bad = any(entry.is_file() for entry in entries)
    elif rule_id in ("rename_images", "rename_videos"):
        names = ("image", "images") if rule_id == "rename_images" else ("video", "videos")
        destination = image_folder if rule_id == "rename_images" else video_folder
        target = Path(folder) / destination
        with os.scandir(folder) as entries:
            bad = not target.is_dir() or any(entry.is_dir(follow_symlinks=False) and entry.name.lower() in names
                                             and str(Path(entry.path)) != str(target) for entry in entries)
    elif rule_id in ("video_extensions", "photo_extensions", "data_extensions"):
        directory, extensions = {
            "video_extensions": (video_folder, video_extensions),
            "photo_extensions": (image_folder, image_extensions),
            "data_extensions": (data_folder, data_extensions),
        }[rule_id]
        suffixes = {value.strip().lstrip(".").lower() for value in extensions.split(";") if value.strip()}
        destination = Path(folder) / directory
        with os.scandir(folder) as entries:
            if not suffixes:
                return "OK"
            for entry in entries:
                path = Path(entry.path)
                if entry.is_file() and path.suffix.lstrip(".").lower() in suffixes \
                        and (rule_id != "data_extensions" or path.parent != destination):
                    return "BAD"
                if entry.is_dir(follow_symlinks=False) and path != destination and entry.name.lower() in suffixes:
                    with os.scandir(path) as children:
                        if any(child.is_file() and (rule_id != "data_extensions"
                               or Path(child.name).suffix.lstrip(".").lower() in suffixes) for child in children):
                            return "BAD"
                if entry.is_dir(follow_symlinks=False) and path == destination:
                    with os.scandir(path) as children:
                        for child in children:
                            if child.is_dir(follow_symlinks=False) and child.name.lower() in suffixes:
                                with os.scandir(child.path) as files:
                                    if any(file.is_file() and (rule_id != "data_extensions"
                                           or Path(file.name).suffix.lstrip(".").lower() in suffixes) for file in files):
                                        return "BAD"
        return "OK"
    elif rule_id in ("flatten_videos", "flatten_images"):
        destination = folder / (video_folder if rule_id == "flatten_videos" else image_folder)
        pending = [destination]
        while pending:
            directory = pending.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                    elif entry.is_file() and directory != destination:
                        return "BAD"
        return "OK"
    elif rule_id in ("non_video_to_root", "non_image_to_root"):
        directory, extensions = (video_folder, video_extensions) if rule_id == "non_video_to_root" else (image_folder, image_extensions)
        suffixes = {value.strip().lstrip(".").lower() for value in extensions.split(";") if value.strip()}
        with os.scandir(folder / directory) as entries:
            bad = any(entry.is_file() and Path(entry.path).parent != folder
                      and Path(entry.name).suffix.lstrip(".").lower() not in suffixes for entry in entries)
    elif rule_id == "remove_empty_dirs":
        pending = [Path(folder)]
        while pending:
            with os.scandir(pending.pop()) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        with os.scandir(entry.path) as children:
                            if not any(True for _ in children):
                                return "BAD"
                        pending.append(Path(entry.path))
        return "OK"
    elif rule_id == "music_videos":
        suffixes = {value.strip().lstrip(".").lower() for value in video_extensions.split(";") if value.strip()}
        with os.scandir(folder / video_folder) as entries:
            files = sorted(Path(entry.path) for entry in entries
                           if entry.is_file() and Path(entry.name).suffix.lstrip(".").lower() in suffixes)
        with worker_results(MusicAnalysis(audio_classes, ffprobe), files, music_threads) as results:
            for path, result in results:
                if result.contains_music:
                    return "BAD"
        return "OK"
    elif rule_id in ("landscape", "landscape_images"):
        directory = video_folder if rule_id == "landscape" else image_folder
        target = Path(folder) / directory / landscape_folder
        with os.scandir(folder):
            if not target.exists():
                return "BAD"
        with os.scandir(target) as entries:
            for entry in entries:
                return "OK" if is_landscape(Path(entry.path), ffprobe) else "BAD"
        return "BAD"
    return "BAD" if bad else "OK"


def merge_folder(source: Path, target: Path, root: Path, enumerate_conflicts: bool, control, identifier):
    target.mkdir(parents=True, exist_ok=True)
    processed = moved = 0
    with os.scandir(source) as entries:
        children = sorted((Path(entry.path), entry.is_dir(follow_symlinks=False)) for entry in entries)
    for child, is_directory in children:
        if control is not None and not control.checkpoint():
            return processed, moved
        destination = target / child.name
        if is_directory and destination.is_dir():
            child_processed, child_moved = merge_folder(child, destination, root, enumerate_conflicts, control, identifier)
            processed += child_processed
            moved += child_moved
            if control is not None and control.stopped:
                return processed, moved
            continue
        if not is_directory:
            processed += 1
        if os.path.lexists(destination) and not enumerate_conflicts:
            report(f"[{identifier}] Skipped name conflict: {child.relative_to(root)} → {destination.relative_to(root)}", flush=True)
            continue
        number = 1
        while os.path.lexists(destination):
            name = f"{child.name}_{number}" if is_directory else f"{child.stem}_{number}{child.suffix}"
            destination = target / name
            number += 1
        child.rename(destination)
        if not is_directory:
            moved += 1
        report(f"[{identifier}] Moved: {child.relative_to(root)} → {destination.relative_to(root)}", flush=True)
    if not any(source.iterdir()):
        source.rmdir()
    return processed, moved


def conform(folder: Path, rules: list[dict], landscape_folder: str, ffprobe: Path,
            video_folder: str, image_folder: str, video_extensions: str, image_extensions: str,
            data_folder: str, data_extensions: str, control=None, enumerate_conflicts: bool = False,
            music_folder="with-music", audio_classes=DEFAULT_AUDIO_CLASSES, empty_file_name=".forceGallery",
            worker_threads=DEFAULT_WORKER_THREADS):
    files_processed = files_moved = folders_renamed = 0
    enabled_rules = [rule for rule in rules if rule["enabled"]]
    for rule_id, group in groupby(enabled_rules, key=lambda rule: rule["id"]):
        if rule_id in ("landscape", "landscape_images", "extension", "music_videos"):
            source_folder = {"landscape": folder / video_folder,
                             "landscape_images": folder / image_folder, "extension": folder,
                             "music_videos": folder / video_folder}[rule_id]
            extensions = image_extensions if rule_id == "landscape_images" else video_extensions
            processed, moved = conform_files(source_folder, list(group), landscape_folder, ffprobe, extensions,
                                            control, enumerate_conflicts, music_folder, audio_classes,
                                            worker_threads[rule_id] if rule_id != "extension" else 1)
            files_processed += processed
            files_moved += moved
            if control is not None and control.stopped:
                break
            continue
        for rule in group:
            if control is not None and not control.checkpoint():
                break
            identifier = RULE_IDENTIFIERS[rule["id"]]
            if rule["id"] == "create_empty_file":
                (folder / empty_file_name).touch()
                files_processed += 1
                report(f"[1/1] [{identifier}] Created empty file: {empty_file_name}", flush=True)
                continue
            if rule["id"] == "video_extensions":
                files = video_files(folder, video_folder, video_extensions)
                destination = folder / video_folder
                for index, source in enumerate(files, 1):
                    if control is not None and not control.checkpoint():
                        break
                    target = destination / source.name
                    if os.path.lexists(target) and not enumerate_conflicts:
                        report(f"[{identifier}] Skipped name conflict: {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
                    else:
                        number = 1
                        while os.path.lexists(target):
                            target = destination / f"{source.stem}_{number}{source.suffix}"
                            number += 1
                        destination.mkdir(parents=True, exist_ok=True)
                        source.rename(target)
                        files_moved += 1
                        report(f"[{identifier}] {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
                    files_processed += 1
                    report(f"[{index}/{len(files)}] [{identifier}] {source.name}", flush=True)
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
                        report(f"[{identifier}] Skipped name conflict: {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
                    else:
                        number = 1
                        while os.path.lexists(target):
                            target = destination / f"{source.stem}_{number}{source.suffix}"
                            number += 1
                        destination.mkdir(parents=True, exist_ok=True)
                        source.rename(target)
                        files_moved += 1
                        report(f"[{identifier}] {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
                    files_processed += 1
                    report(f"[{index}/{len(files)}] [{identifier}] {source.name}", flush=True)
                if control is not None and control.stopped:
                    break
                continue
            if rule["id"] == "data_extensions":
                files = data_files(folder, data_folder, data_extensions)
                destination = folder / data_folder
                for index, source in enumerate(files, 1):
                    if control is not None and not control.checkpoint():
                        break
                    target = destination / source.name
                    if os.path.lexists(target) and not enumerate_conflicts:
                        report(f"[{identifier}] Skipped name conflict: {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
                    else:
                        number = 1
                        while os.path.lexists(target):
                            target = destination / f"{source.stem}_{number}{source.suffix}"
                            number += 1
                        destination.mkdir(parents=True, exist_ok=True)
                        source.rename(target)
                        files_moved += 1
                        report(f"[{identifier}] {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
                    files_processed += 1
                    report(f"[{index}/{len(files)}] [{identifier}] {source.name}", flush=True)
                if control is not None and control.stopped:
                    break
                continue
            if rule["id"] in ("flatten_videos", "flatten_images", "non_video_to_root", "non_image_to_root"):
                video = rule["id"] in ("flatten_videos", "non_video_to_root")
                media_folder = folder / (video_folder if video else image_folder)
                files = []
                if rule["id"] in ("flatten_videos", "flatten_images"):
                    destination = media_folder
                    pending = [media_folder]
                    while pending:
                        directory = pending.pop()
                        with os.scandir(directory) as entries:
                            for entry in entries:
                                if entry.is_dir(follow_symlinks=False):
                                    pending.append(Path(entry.path))
                                elif entry.is_file() and directory != media_folder:
                                    files.append(Path(entry.path))
                else:
                    destination = folder
                    extensions = video_extensions if video else image_extensions
                    suffixes = {value.strip().lstrip(".").lower() for value in extensions.split(";") if value.strip()}
                    with os.scandir(media_folder) as entries:
                        files = [Path(entry.path) for entry in entries
                                 if entry.is_file() and Path(entry.path).parent != destination
                                 and Path(entry.name).suffix.lstrip(".").lower() not in suffixes]
                for index, source in enumerate(sorted(files), 1):
                    if control is not None and not control.checkpoint():
                        break
                    target = destination / source.name
                    if os.path.lexists(target) and not enumerate_conflicts:
                        report(f"[{identifier}] Skipped name conflict: {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
                    else:
                        number = 1
                        while os.path.lexists(target):
                            target = destination / f"{source.stem}_{number}{source.suffix}"
                            number += 1
                        source.rename(target)
                        files_moved += 1
                        report(f"[{identifier}] {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
                    files_processed += 1
                    report(f"[{index}/{len(files)}] [{identifier}] {source.name}", flush=True)
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
                    report(f"[{identifier}] Removed empty folder: {directory.relative_to(folder)}", flush=True)
                report(f"[{identifier}] Removed {removed} empty folders.", flush=True)
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
                    report(f"[{index}/{len(sources)}] [{identifier}] Renamed folder: {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
                else:
                    processed, moved = merge_folder(source, target, folder, enumerate_conflicts, control, identifier)
                    files_processed += processed
                    files_moved += moved
                    if control is not None and control.stopped:
                        break
                    report(f"[{index}/{len(sources)}] [{identifier}] Merged folder: {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
            target.mkdir(parents=True, exist_ok=True)
        if control is not None and control.stopped:
            break
    report(f"Completed: {files_processed} files processed, {files_moved} files moved, "
          f"{folders_renamed} folders renamed.", flush=True)


def conform_files(folder: Path, rules: list[dict], landscape_folder: str, ffprobe: Path, extensions: str, control=None, enumerate_conflicts: bool = False,
                  music_folder="with-music", audio_classes=DEFAULT_AUDIO_CLASSES, threads=1):
    identifier = RULE_IDENTIFIERS[rules[0]["id"]]
    suffixes = {value.strip().lstrip(".").lower() for value in extensions.split(";") if value.strip()}
    files = []
    report(f"[{identifier}] Scanning {folder}", flush=True)
    with os.scandir(folder) as entries:
        for checked, entry in enumerate(entries, 1):
            if entry.is_file():
                files.append(Path(entry.path))
            if checked % 500 == 0:
                report(f"[{identifier}] Scanning: {checked} entries checked, {len(files)} files found", flush=True)
    files.sort()
    report(f"[{identifier}] Found {len(files)} files", flush=True)
    moved = 0
    processed = 0
    music_analysis = MusicAnalysis(audio_classes, ffprobe, control)

    def destination_for(source):
        if control is not None and not control.checkpoint():
            return folder
        destination = folder
        for rule in rules:
            if not rule["enabled"]:
                continue
            if rule["id"] in ("landscape", "landscape_images"):
                if source.suffix.lstrip(".").lower() in suffixes and is_landscape(source, ffprobe):
                    destination /= landscape_folder
            elif rule["id"] == "music_videos":
                if source.suffix.lstrip(".").lower() in suffixes:
                    result = music_analysis(source)
                    if control is not None and control.stopped:
                        return folder
                    report(f"[{identifier}] Music: {source.name}, score={result.max_window_score:.6f}, thresholds={result.thresholds}", flush=True)
                    if result.contains_music:
                        destination /= music_folder
            elif rule["id"] == "extension":
                destination /= source.suffix.lstrip(".").lower() or "no-extension"
        return destination

    with worker_results(destination_for, files, threads) as results:
        for index, (source, destination) in enumerate(results, 1):
            if control is not None and (control.stopped or (threads > 1 and not control.checkpoint())):
                break
            target = destination / source.name if destination != folder else source
            if target != source:
                if os.path.lexists(target) and not enumerate_conflicts:
                    report(f"[{identifier}] Skipped name conflict: {source.relative_to(folder)} → {target.relative_to(folder)}", flush=True)
                else:
                    number = 1
                    while os.path.lexists(target):
                        target = destination / f"{source.stem}_{number}{source.suffix}"
                        number += 1
                    destination.mkdir(parents=True, exist_ok=True)
                    source.rename(target)
                    moved += 1
                    report(f"[{identifier}] {source.name} → {target.relative_to(folder)}", flush=True)
            report(f"[{index}/{len(files)}] [{identifier}] {source.name}", flush=True)
            processed += 1
    return processed, moved
