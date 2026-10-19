# FolderConformer

A basic Windows Qt Quick application for moving files into folders using an ordered rule pipeline. All controls use the standard Qt appearance.

Select a folder, enable the desired rules, use **Move up / Move down** to set their order, and choose **Start moving files**. By default, file rules process direct files and folder rules process direct subfolders. Enable subdirectories to include nested files and folders.

- **Landscape and square media:** ffprobe reads the first video/image stream. Display dimensions account for sample aspect ratio and rotation. Media with width/height ≥ 1 goes into the configured folder (default `Landscape-FULL`).
- **Extension:** files go into lowercase final-extension folders, such as `txt` or `png`. Files without an extension go into `no-extension`.

- **Rename image folders:** case-insensitive `image` and `images` become `photo`.
- **Rename video folders:** case-insensitive `video` and `videos` become `video`.
- **Group image extension folders:** move `jpg`, `jpeg`, `png`, `webp`, and `heic` folders, with their contents, into `photo/`. GIF is excluded.
- **Group video extension folders:** move `mp4`, `ts`, `m4v`, `wmv`, `avi`, `mov`, `mkv`, `webm`, `mpg`, `mpeg`, `mts`, `m2ts`, `m2v`, `vob`, `flv`, `3gp`, `3g2`, `ogv`, and `asf` folders into `video/`.

Folder rules match whole folder names without regard to case, preserving extension-folder spelling. Already grouped extension folders stay in place. Each folder rule runs at its position in the list, so put it after Extension to group newly created extension folders. Rename collisions stop the run without merging folders.

Each matching file rule adds a folder to the destination. Landscape then extension gives `Landscape-FULL/png/photo.png`; extension then landscape gives `png/Landscape-FULL/photo.png`. Disabled rules add nothing. Consecutive file rules compose one destination before moving files. Folder rules then operate on the resulting folders. Existing same-name files are never replaced on Windows: the rename fails and the run stops. Earlier moves remain in place. The log shows raw failures; there is no automatic recovery.

The input folder, landscape folder name, recursive scanning checkbox, all six rule toggles and rule order save automatically using QSettings in the platformdirs user configuration directory (`%LOCALAPPDATA%/FolderConformer/FolderConformer.ini` on Windows).

## Development

The existing mise Python 3.12 environment is retained. Dependencies, including the FFmpeg provider, are managed through uv and locked in `uv.lock`.

```powershell
mise exec -- uv sync --locked
uv run folderconformer
mise run run
mise run test
```

`prepare-tools` obtains FFmpeg 8.0.1 and ffprobe from `static-ffmpeg==3.0`, stages private copies under `build/tools`, and records SHA-256 hashes and build configuration. The installed application uses its bundled copies and does not download tools at runtime.

## Windows installer

Set `ISCC_PATH` to the installed Inno Setup compiler, then run:

```powershell
$env:ISCC_PATH = 'C:\Users\shoji\AppData\Local\Programs\Inno Setup 6\ISCC.exe'
mise run build
```

The build reads version metadata from `pyproject.toml`, freezes an onedir application, and compiles `dist/installer/FolderConformer-Windows-Setup-0.3.0.exe`. Installation is per-user, with a Start menu shortcut and an optional desktop shortcut. Settings are stored outside the installation and survive upgrades/uninstall.
