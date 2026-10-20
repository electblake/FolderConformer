# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Moved the video and image extension controls into a native Files dock below Folders on the right, with View > Files to hide or reopen it.

## [0.6.0] - 2026-10-20

### Changed

- Moved all three destination folder controls out of the Folders field group into a native, movable Qt dock widget, initially docked on the right.
- Added View > Folders to hide or reopen the dock and preserved automatic settings, destination validation, themes, and processing/update locks.

## [0.5.4] - 2026-10-19

### Changed

- Moved Download Update and Quit and Install beside the other update buttons and sized the Software Update dialog to fit the row.

## [0.5.3] - 2026-10-19

### Added

- Added a checked-by-default Launch FolderConformer checkbox on the installer's completion page, skipped during silent installations.

## [0.5.2] - 2026-10-19

### Added

- Added Run Once before each rule's move buttons to run that rule alone without changing saved rule settings.
- Added Open Output Folder at the bottom left beside the output controls.

## [0.5.1] - 2026-10-19

### Added

- Added the MIT license and included it in the installed application and Python package.
- Added the standard Inno Setup license agreement page requiring acceptance during interactive installation.

## [0.5.0] - 2026-10-19

### Added

- Added File > Settings with Data and Appearance field groups and moved the configuration folder controls into Data.
- Added a qt-themes dropdown persisted through QSettings and a Restart & Apply button to relaunch with the selected theme.
- Added a right-aligned Copy Output button below the activity log to select and copy all output to the clipboard.
- Added File > Select Folder.. to set the input folder through the existing picker, followed by a divider and Quit.

### Changed

- Selected Blender as the default theme for new configurations while preserving saved theme choices.
- Replaced custom rounded rule badges with standard Qt labels.
- Renamed Help > Extras to Help > Install for File Explorer and simplified the dedicated installation dialog to an explanation, status, and Install / Close buttons.

### Fixed

- Applied theme palettes to QML windows and their controls, including active, inactive, and disabled colors.

## [0.4.1] - 2026-10-19

### Added

- Added blue and pink icons and logotypes in engineering and casual styles.

### Changed

- Applied the blue engineering icon to the application, Explorer integration, installer, uninstall entry, and shortcuts.
- Added the blue engineering logotype to the README with a maximum width of 640 pixels.

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
