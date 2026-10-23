<img src="assets/blue/logotype-eng-style.png" alt="FolderConformer" width="640" style="max-width: 640px; width: 100%; height: auto;">

# FolderConformer

A basic Windows Qt Quick application for moving files into folders using an ordered rule pipeline. Controls use the Blender theme by default.

Select a folder, enable the desired rules, use **Move up / Move down** to set their order, and choose **Execute rules**. Rules define their own scan depth: N4 processes loose files at the input root, H2, B7, and M5 process direct files in their configured video and photo folders, F8 and N2 create or consolidate their media folders, J1, S6, and R3 inspect their specific extension folders, and K9 removes empty directories recursively.

Each rule has a permanent, randomly assigned letter–number identifier before its file/folder label: **H2** move landscape and square videos, **N4** group loose files by extension, **F8** single images folder, **N2** single videos folder, **J1** move image file extensions, **S6** move video file extensions, and **K9** remove empty directories, and **B7** move landscape and square images, and **R3** move data files into Data folder, and **M5** move videos containing music. Identifiers stay with their rules across reordering and restarts and do not indicate execution order.

Choose **Help > Install for File Explorer**, then **Install**, to add **Open in FolderConformer** to right-click menus for folders, folder backgrounds, and drives for your Windows account. Explorer opens the selected directory in the folder field without starting processing. Reinstalling updates the same menu entries.

- **H2 — Move landscape and square videos:** inspect matching video files directly inside the configured video folder. Files with displayed width/height ≥ 1 move into its configured landscape subfolder (default `video/Landscape-FULL/`).
- **B7 — Move landscape and square images:** apply the same aspect-ratio behavior to matching image files directly inside the configured photo folder (default destination `photo/Landscape-FULL/`). Both rules use their configured extension lists, account for sample aspect ratio and rotation through ffprobe, and respect Resolve name conflicts. Portraits, other file types, input-root media, and deeper subfolders stay in place. Neither rule is recursive.
- **N4 — Group loose files by extension:** only files directly in the input folder go into lowercase final-extension folders, such as `txt` or `png`. Files without an extension go into `no-extension`.

- **F8 — Single images folder:** create the configured images folder if missing, or rename an immediate `image`/`images` folder into it. Merge remaining aliases into the destination, preserving nested contents.
- **N2 — Single videos folder:** create the configured videos folder if missing, or rename an immediate `video`/`videos` folder into it. Merge remaining aliases into the destination. Both rules match aliases without regard to case, merge shared subdirectories, and skip or number conflicting names according to Resolve name conflicts. Empty merged source folders are removed.
- **J1 — Move images into images folder:** move matching image files from the input root, and files directly inside image-extension folders at the root or inside the configured photo folder, into that photo folder (default `photo/`). For example, `jpg/image.jpg` and `photo/jpg/image.jpg` move to `photo/image.jpg`. Uses the configured image extensions (`jpg`, `jpeg`, `png`, `webp`, and `heic` by default; GIF excluded). Direct sidecar files move with the extension-folder contents. Deeper folders stay in place without recursive scanning. Empty folders remain for K9, and name conflicts are skipped or numbered according to Resolve name conflicts.
- **S6 — Move videos into videos folder:** move matching video files from the input root into the configured video folder (default `video/`). Also move files directly inside video-extension folders at the input root or directly inside the video folder, such as `mp4/clip.mp4` and `video/mp4/clip.mp4`, into `video/clip.mp4`. Extension folders use the configured video extension list; their direct files, including sidecar files, move together. Deeper folders and unrelated folders stay in place without recursive scanning. Empty source folders remain for K9. Name conflicts are skipped or numbered according to Resolve name conflicts.
- **R3 — Move data files into Data folder:** move matching files from the input root and directly inside configured extension folders at the root or inside the Data folder into the configured Data destination (default `Data/`). The Data file extensions setting defaults to `csv;db;txt;`. Only matching files move; unrelated files and deeper folders stay in place. Supports Check, Run Once, reordering, disabling, and Resolve name conflicts.
- **K9 — Remove empty dirs:** recursively remove empty subdirectories, including parents that become empty after their children are removed. The selected input folder is kept.

**Check** is available for every rule. N4 shows **BAD** while loose files remain at the input root. F8 and N2 show **BAD** when their configured destination is missing or immediate legacy folders remain to rename or merge, including skipped conflicts. They show **OK** when no work remains. H2 and B7 show **BAD** when their configured media folder is missing or while landscape or square files remain directly inside it, including skipped conflicts, and **OK** when the folder exists and none remain. Failed checks show **ERR**, with the failure details retained in the log. J1, S6, and R3 show **BAD** while eligible files remain in their source locations, including skipped conflicts, and **OK** when clear. K9 shows **BAD** if empty subdirectories remain and **OK** otherwise. Checks run in a worker process and do not change files. Results start as **-** and clear when the input folder or image/video/data/landscape configuration changes, or when rule execution starts. Click Check again to refresh.

Folder-name matching ignores case. F8 and N2 consolidate only the matching folders at the input root, preserving their nested structure when merging. Unrelated folders remain untouched.

Each rule runs at its position in the list. H2 and B7 organize files inside their respective media folders; N4 only groups input-root files by extension. Run J1/S6 before B7/H2 to collect loose media before sorting it by aspect ratio. Disabled rules do not run. Existing same-name files are never replaced. In the Files dock, enable **Resolve name conflicts (_1, _2, …)** to use the first available numbered name before the extension, such as `photo_1.jpg`. This checkbox is saved and defaults to unchecked: conflicting files stay in their source location, are logged as skipped, and processing continues. Other failures remain visible in the log.

The native **Folders** dock on the right contains the landscape destination (default `Landscape-FULL`), video destination (default `video/`), image destination (default `photo/`), and Data destination (default `Data/`). Drag its title bar to dock it on another side or float it in a separate window. Use **View > Folders** to hide or reopen it. Folder rules use the configured destinations. The native **Files** dock starts below Folders on the right and contains semicolon-separated video, image, and data extension lists used to match extension folders. It can also be moved or floated; use **View > Files** to hide or reopen it. **View > Reset Layout** restores both docks on the right, with Files below Folders, and reopens any closed dock. The defaults are the lists above; add `gif` to the image list to include GIF folders. Matching ignores case, surrounding whitespace, and leading dots.

The input folder, destination folders, extension lists, all rule toggles and rule order save automatically using QSettings in the platformdirs user configuration directory (`%LOCALAPPDATA%/FolderConformer/FolderConformer.ini` on Windows). The main window geometry and both docks' positions, sizes, floating state, and visibility are saved on close or Restart & Apply and restored on the next launch using Qt's built-in state APIs. In **File > Settings > Data**, browse for a different configuration folder or edit its path and finish editing to save the current settings there. The default configuration file remembers that location for future launches. **Open** opens the selected configuration folder.

**File > Settings > Appearance** provides one theme dropdown with **System default** and the [qt-themes](https://github.com/beatreichenbach/qt-themes) palettes. Blender is selected by default for new configurations. The selection is saved through QSettings. Click **Restart & Apply** beside the dropdown to relaunch with the selected theme. System default keeps Qt’s platform style; a selected color theme uses Qt’s built-in Fusion controls so the palette applies consistently.

## Development

### Video music detection

**M5 — Move videos containing music** analyzes every audio track and channel of matching videos directly inside the configured video folder using Google's pretrained YAMNet 1. Music-positive files move into its **Music Video folder**, default `video/with-music/`. Photos, input-root files, and nested folders are outside this rule. Files without audio remain in place. Decoder/model failures stop the worker and appear in the activity log.

The **Audio** dock starts below Files on the right. It contains the music score threshold (default `0.504`); lower values match more readily. The score is not a probability of correctness. Folder names belong in Folders, while extensions and conflict handling stay in Files. Audio supports View-menu visibility, dragging/floating, saved layouts, and Reset Layout.

Check runs the actual classifier without moving anything. BAD means a music-positive file remains eligible to move, including a name conflict; OK means no work remains. Run Once and Execute rules perform real moves using the existing conflict setting. Pause/Stop is acknowledged between bounded audio batches; stopping leaves the current video unmoved. Cancel terminates the worker.

Run video collection before music detection. Landscape and Music both scan direct children: whichever runs first takes a video matching both. To prioritize music, order video collection, Music, then Landscape. Neither rule scans inside the other's destination.

YAMNet supplies its own features and trained weights. FFmpeg decodes video audio to 16 kHz float PCM; each channel is classified separately so opposing channels cannot cancel. Music, Singing, and Humming scores contribute to the presence decision, including music under speech. Analysis stops after the first batch containing a Music, Singing, or Humming score at or above the threshold. One matching window is sufficient. Batches contain eight windows (4.335 seconds of audio); remaining audio and tracks are skipped after a match. Negative files are scanned through the end. Evidence times are relative to the decoded audio track.

This is a pretrained classifier, with imperfect recognition. The small real-recording evaluation caught a whale-song false positive; it does **not** establish 95% recall or a 1% false-positive rate. See [measured results and limitations](docs/music-detection-results.md). No training or externally supplied model is required to use the feature.

Setup downloads the pinned YAMNet v1 archive from Kaggle, verifies its SHA-256, and installs it below the private venv's `models/yamnet/1` directory. No Kaggle account/API key is required for this public archive. TensorFlow and its dependencies are installed through the lockfile. Microsoft's signed Visual C++ runtime is downloaded and installed by Setup and may request Windows approval. No model or dependency binaries are embedded in the application installer. Classification runs offline and never downloads a missing model.

For development, run `mise run prepare-model` once before using Music. `mise run test` also prepares the model and licensed regression recordings. Evaluate the real model on encoded videos with `uv run python packaging/evaluate_music.py validation` and `uv run python packaging/evaluate_music.py test`. Test fixtures and generated videos stay under `build/music/`; source URLs, hashes, and attribution are recorded in `tests/music-fixtures.json`.

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

The build compiles `dist/installer/FolderConformer-0.8.0-windows-amd64-Setup.exe` from app source, QML, and the lockfile. The filename includes the version, platform, and machine architecture. Setup downloads a pinned, SHA-256-verified uv archive, managed Python 3.12.10, and the locked dependencies. No Python, Qt, FFmpeg, or uv binaries are embedded in Setup.

`platformdirs.user_data_path` places the app venv in `%LOCALAPPDATA%/FolderConformer/runtime/venv`. The uv cache uses `platformdirs.user_cache_path`. Setup syncs the environment without development dependencies and downloads FFmpeg/ffprobe before completing. Start menu and optional desktop shortcuts launch the venv's `pythonw.exe`; workers use its `python.exe`. Uninstall removes the app venv and private cache while retaining settings. uv manages its downloaded Python interpreter in its own per-user storage.

Additional dependencies belong in `pyproject.toml` and `uv.lock`; setup installs them without adding their binaries to the installer. Installation requires internet access. Run `uv run python packaging/smoke.py` to check online installation, the installed app, file processing, reinstall, and uninstall.

### Flattening and non-media files

**V1 — Flatten videos folder** and **I1 — Flatten images folder** recursively move every nested file into the configured media folder's root, including files in landscape/music subfolders. Both default to off. Empty subfolders remain unless **K9 — Remove empty dirs** is enabled; K9 now also defaults to off. Existing saved toggles are preserved.

**V2 — Move non-video files to root** and **I2 — Move non-image files to root** move direct files whose extensions are absent from the corresponding configured extension list into the selected input folder. These rules default to on and do not scan subfolders. Move them after flattening and before collection, data, or extension rules to process misplaced files in the same run. Rules added to saved configurations are appended, preserving the existing order.

All four rules support Check and Run Once and use the existing name-conflict setting.
