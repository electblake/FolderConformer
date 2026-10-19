# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-10-19

### Added

- Added the `uv run folderconformer` application entry point.
- Added a persistent Include subdirectories checkbox, disabled by default, for recursive scanning.
- Added rules to rename `image` / `images` folders to `photo` and `video` / `videos` folders to `video`.
- Added rules to group image extension folders under `photo` (excluding GIF) and video extension folders under `video`.
- Added file/folder rule labels, per-file progress, and completion counts for moved files and changed folders.
- Added regression checks for all six rules, recursive scanning, collisions, UI autosave, and restoration in a fresh process.

### Changed

- Stored automatically saved control values and rule order in QSettings at the platformdirs user configuration path.
- Applied all six individually enabled rules in the configured order, including folder rules between file rules.
- Rebuilt the Windows installer with bundled FFmpeg/ffprobe and the complete six-rule pipeline.

## [0.2.0] - 2026-10-19

### Added

- Added a standard Qt Quick interface with folder selection and individually enabled, reorderable rules.
- Added ffprobe scanning for landscape and square media with a configurable destination folder.
- Added extension grouping and sequential nested rule destinations.
- Added persistent folder, rule order, toggle, and destination settings through QSettings.
- Added bundled FFmpeg tools and a Windows Inno Setup installer.
