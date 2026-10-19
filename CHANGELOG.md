# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-10-19

### Added

- Added Help > Check for updates.. with a window-modal Software Update dialog, GitHub Releases checks, installer downloads, and explicit quit-and-install.
- Added updater checks for numeric version ordering, exact installer selection, responsive networking, progress and button states, blocked busy dismissal, and installation after shutdown.
- Added Help > Extras with per-user File Explorer installation for folders, folder backgrounds, and drives, opening the selected folder without starting processing.
- Added Folders controls for landscape, video, image, and user configuration folders, with Browse and Open actions for the configuration folder.
- Added Files controls for semicolon-separated video and image extension lists, initialized with the existing extension lists.

### Changed

- Matched installer filenames to the updater's platform and architecture lookup while retaining the existing installation identity and location.
- Sourced folder-rule destinations and extension matches from the saved controls and reflected destination changes in rule labels.
- Saved the new controls through QSettings and retained the selected configuration location across restarts.
- Made the settings groups scroll while keeping processing controls and the log visible.
- Replaced the bundled Windows runtime with an online installer that downloads verified uv, installs managed Python, and syncs locked dependencies into a platformdirs user-data venv.
- Installed FFmpeg and ffprobe during setup through the uv-managed dependency instead of embedding executables in Setup.
- Launched the installed Python package directly and removed the PyInstaller build.

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
