<img src="assets/blue/logotype-eng-style.png" alt="FolderConformer" width="640" style="max-width: 640px; width: 100%; height: auto;">

# FolderConformer

A basic Windows Qt Quick application for moving files into folders using an ordered rule pipeline. Controls use the Blender theme by default.

Select a folder, enable the desired rules, use **Move up / Move down** to set their order, and choose **Start moving files**. By default, file rules process direct files and folder rules process direct subfolders. Enable subdirectories to include nested files and folders.

Choose **Help > Install for File Explorer**, then **Install**, to add **Open in FolderConformer** to right-click menus for folders, folder backgrounds, and drives for your Windows account. Explorer opens the selected directory in the folder field without starting processing. Reinstalling updates the same menu entries.

- **Landscape and square media:** ffprobe reads the first video/image stream. Display dimensions account for sample aspect ratio and rotation. Media with width/height ≥ 1 goes into the configured folder (default `Landscape-FULL`).
- **Extension:** files go into lowercase final-extension folders, such as `txt` or `png`. Files without an extension go into `no-extension`.

- **Rename image folders:** case-insensitive `image` and `images` become `photo`.
- **Rename video folders:** case-insensitive `video` and `videos` become `video`.
- **Group image extension folders:** move `jpg`, `jpeg`, `png`, `webp`, and `heic` folders, with their contents, into `photo/`. GIF is excluded.
- **Group video extension folders:** move `mp4`, `ts`, `m4v`, `wmv`, `avi`, `mov`, `mkv`, `webm`, `mpg`, `mpeg`, `mts`, `m2ts`, `m2v`, `vob`, `flv`, `3gp`, `3g2`, `ogv`, and `asf` folders into `video/`.

Folder rules match whole folder names without regard to case, preserving extension-folder spelling. Already grouped extension folders stay in place. Each folder rule runs at its position in the list, so put it after Extension to group newly created extension folders. Rename collisions stop the run without merging folders.

Each matching file rule adds a folder to the destination. Landscape then extension gives `Landscape-FULL/png/photo.png`; extension then landscape gives `png/Landscape-FULL/photo.png`. Disabled rules add nothing. Consecutive file rules compose one destination before moving files. Folder rules then operate on the resulting folders. Existing same-name files are never replaced on Windows: the rename fails and the run stops. Earlier moves remain in place. The log shows raw failures; there is no automatic recovery.

The native **Folders** dock on the right contains the landscape destination (default `Landscape-FULL`), video destination (default `video/`), and image destination (default `photo/`). Drag its title bar to dock it on another side or float it in a separate window. Use **View > Folders** to hide or reopen it. Folder rules use the configured destinations. The native **Files** dock starts below Folders on the right and contains semicolon-separated video and image extension lists used to match extension folders. It can also be moved or floated; use **View > Files** to hide or reopen it. The defaults are the lists above; add `gif` to the image list to include GIF folders. Matching ignores case, surrounding whitespace, and leading dots.

The input folder, destination folders, extension lists, recursive scanning checkbox, all six rule toggles and rule order save automatically using QSettings in the platformdirs user configuration directory (`%LOCALAPPDATA%/FolderConformer/FolderConformer.ini` on Windows). In **File > Settings > Data**, browse for a different configuration folder or edit its path and finish editing to save the current settings there. The default configuration file remembers that location for future launches. **Open** opens the selected configuration folder.

**File > Settings > Appearance** provides one theme dropdown with **System default** and the [qt-themes](https://github.com/beatreichenbach/qt-themes) palettes. Blender is selected by default for new configurations. The selection is saved through QSettings. Click **Restart & Apply** beside the dropdown to relaunch with the selected theme. System default keeps Qt’s platform style; a selected color theme uses Qt’s built-in Fusion controls so the palette applies consistently.

## Development

The existing mise Python 3.12 environment is retained. Dependencies, including the FFmpeg provider, are managed through uv and locked in `uv.lock`.

```powershell
mise exec -- uv sync --locked
uv run folderconformer
mise run run
mise run test
```

`prepare-tools` obtains FFmpeg and ffprobe through `static-ffmpeg==3.0` inside the project environment. The installed application reads the tools from its own environment; setup downloads them before the app is launched.

## Windows installer

Set `ISCC_PATH` to the installed Inno Setup compiler, then run:

```powershell
$env:ISCC_PATH = 'C:\Users\shoji\AppData\Local\Programs\Inno Setup 6\ISCC.exe'
mise run build
```

The build compiles `dist/installer/FolderConformer-0.6.0-windows-amd64-Setup.exe` from app source, QML, and the lockfile. The filename includes the version, platform, and machine architecture. Setup downloads a pinned, SHA-256-verified uv archive, managed Python 3.12.10, and the locked dependencies. No Python, Qt, FFmpeg, or uv binaries are embedded in Setup.

`platformdirs.user_data_path` places the app venv in `%LOCALAPPDATA%/FolderConformer/runtime/venv`. The uv cache uses `platformdirs.user_cache_path`. Setup syncs the environment without development dependencies and downloads FFmpeg/ffprobe before completing. Start menu and optional desktop shortcuts launch the venv's `pythonw.exe`; workers use its `python.exe`. Uninstall removes the app venv and private cache while retaining settings. uv manages its downloaded Python interpreter in its own per-user storage.

Additional dependencies belong in `pyproject.toml` and `uv.lock`; setup installs them without adding their binaries to the installer. Installation requires internet access. Run `uv run python packaging/smoke.py` to check online installation, the installed app, file processing, reinstall, and uninstall.
