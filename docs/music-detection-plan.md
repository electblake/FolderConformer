# Video music detection: FolderConformer implementation plan

Reviewed 2026-10-23. Planning only; implementation waits until the other active changes are finished and committed. Re-read the committed rules, docks, worker protocol, and installer before editing them. The inspected checkout had concurrent changes in app.py, QML, tests, and CHANGELOG.md.

## Complete outcome

Install FolderConformer through Setup, select a folder containing videos, enable the music rule, and execute it. The installed application decodes each eligible video, runs a real pretrained classifier locally, and moves music-positive videos to the configured music subfolder. Negative videos stay in place. Photos are outside this rule.

No supplied-model field, untrained estimator, mocked classifier, external manual preparation, or deferred core implementation counts as delivery. The implementation owns model acquisition, dependency installation, inference, evaluation, settings, moves, and installed-app end-to-end verification.

## Replace the raw proposal's incomplete classifier path

Use Google's pretrained **YAMNet v1 SavedModel**, executed with TensorFlow on Windows CPU, as the primary detector. The original librosa/HistGradientBoosting proposal supplies feature code but no learned decision model. Building that proposal would require an additional training project before it could classify music. YAMNet already provides trained event classification and its own feature extraction.

Use the SavedModel directly through `tf.saved_model.load(local_model_directory)`. Do not rebuild the model from Keras source or recreate its spectral features. Do not add librosa, scikit-learn, joblib, training manifests, or model training to the app merely because they appeared in the raw proposal. FFmpeg already supplies the video decoder and resampler.

Verified research:

- The official tutorial describes pretrained classification for 521 AudioSet classes.
- Its class map includes Music (`/m/04rlf`), Singing (`/m/015lz1`), and Humming (`/m/02fxyj`). Resolve their indices from the model asset, rather than guessing numeric columns.
- Inputs are one-dimensional float32 waveforms at 16 kHz. The model supplies feature extraction, overlapping predictions, and short-input/end padding.
- The model's source uses 0.96-second spectral patches at a 0.48-second hop; the first complete waveform context is 0.975 seconds. These are not interchangeable lengths.
- TensorFlow documents native Windows CPU installation and publishes a Python 3.12 Windows wheel. Begin dependency qualification with TensorFlow 2.21.0 against the app's managed Python 3.12.10; freeze the successful resolved environment in uv.lock.
- The versioned archive was downloaded and inspected during this review. It contains `saved_model.pb`, variables, and `assets/yamnet_class_map.csv`; compressed size was 14,242,921 bytes. Observed SHA-256: `b80da2a1a56926fb0767205051a200dd7b3beaf3ea1ea126c42a53943996e5e0`.

This establishes an available pretrained implementation path, not measured FolderConformer accuracy. No inference or installed-app test was run during this planning review.

## Effort 1: real detector and setup delivery

### Production inference

Add a small `folderconformer/music.py` integration module consistent with the existing flat package. Load the local model once per worker that performs music analysis. Keep TensorFlow imports and inference outside the UI process.

1. Use the installed absolute ffprobe path to enumerate the video's audio streams.
2. Analyze all audio streams and each channel independently. Do not average channels, which can cancel opposite-polarity audio. No audio streams is a valid no-music case, not a decoder failure.
3. Use the installed FFmpeg to decode and resample to normalized 16 kHz float32 PCM, preserving channels. Use one decoder path, with its normal nonzero-exit behavior. No alternative decoder, online service, or runtime download.
4. Feed bounded contexts to the original SavedModel. Preserve its global 0.48-second frame grid and sufficient waveform overlap; apply model end padding only at the actual end. Compare chunked predictions against the original model called on complete short recordings. Do not use independent arbitrary chunks that manufacture internal padded boundaries.
5. Scan the complete recording. Retain bounded audio and feature memory; collect compact evidence with stream, channel, class, score, and timestamps. Include start-time offsets when reporting video-relative evidence.
6. Use music-related class scores rather than the top winning class: simultaneous speech must not veto music. The initial semantic mapping is Music, Singing, and Humming. Measure that mapping on a cappella, instrumental, background music, and hard negatives before freezing it.
7. Decide presence using the maximum selected score across frames, channels, and streams against an evaluated threshold. Do not average away a brief musical passage. Call it a score, not a calibrated file probability.
8. Integrate the existing worker's progress and pause/stop controls at bounded analysis intervals. Stop must terminate the active decoder and prevent moving the current incompletely analyzed video. A cancelled scan must not produce a negative classification or a completed move.

Use dependency behavior for short waveforms, silence, spectral features, padding, and numerical operations. Remove the raw proposal's arbitrary 0.5-second rejection. Short clips still need measured sensitivity; library padding is not proof of accurate classification.

Respect the user's fail-fast policy: no new custom exception hierarchy, catching/wrapping failures, input-validation error branches, automatic retry, heuristic substitution, or conversion of failures into False. Preserve the app's existing worker exit/log reporting. Release-time tests establish model/package contracts; do not build a runtime compatibility framework.

### Install everything through Setup

Keep the existing source + lockfile online installer architecture. Dependencies and model bytes must not be embedded into the application installer executable.

- Add the qualified TensorFlow dependency to pyproject.toml and resolve its exact dependencies through uv.lock. Existing `packaging/install_runtime.py` installs them using locked uv sync into the private runtime venv.
- Download the versioned YAMNet archive during Setup, using Inno's download/integrity/extraction support. The reviewed source is `https://tfhub.dev/google/yamnet/1?tf-hub-format=compressed`. Record the actual archive format and uncompressed size for the installer directives; do not mistake compressed length for extracted size.
- Install the complete model under the app-owned runtime, e.g. `runtime/models/yamnet/1/`. Application code uses that fixed local location. No model picker, first-use download, or reliance on a developer's TensorFlow Hub cache.
- Pin the artifact digest in installer release inputs. A failed download or extraction fails setup through its native operation, without mirrors or retries. Check the model license and include its required notices before release.
- Account for TensorFlow's documented native Windows Visual C++ runtime prerequisite in Setup. Use the official redistributable and supported unattended installation, not an assumption that the developer machine represents a clean install.
- After dependencies and model are installed, run a real local model invocation from the installed interpreter as part of setup verification. Confirm installer exit status propagates failure through the existing setup flow.
- Keep the same setup-driven dependency/model installation path for upgrades. Preserve settings, install the model required by the app version, and verify uninstall removes the owned model with the existing runtime directory.
- Development preparation must acquire the same pinned model explicitly; classification itself never fetches it. Training corpora and test videos are test assets, not consumer setup downloads.

## Effort 2: folders, Audio dock, and saved settings

Follow the native QDockWidget implementation now present in app.py; do not recreate the removed FolderPanel.qml.

- Add **Music Video folder** to the Folders dock. Controller/QSettings name: `musicVideoFolder`; default: `with-music`, following the explicit requested default. Example destination: `video/with-music/`. A user can configure `With-Music` or another folder name.
- Add native **Audio** dock with stable object name `audioDock`. Initially dock it on the right, vertically below Files. Add View > Audio and include it in Reset Layout, state persistence, visibility synchronization, theme behavior, close/restart, and disabled-during-run/update behavior.
- Place the music score threshold control in Audio, with its initial value established by evaluation, not an arbitrary 0.5. Persist a user-selected threshold in QSettings and pass it to both Check and Execute. Explain that lower thresholds match more readily; the value is not a probability of correctness.
- Show installed model/version and the fixed “music anywhere in the video” behavior in Audio. Do not expose FFT parameters, a model path, training controls, or provider selection.
- Rule enablement and order remain in Rules. Folder names remain in Folders; video extensions and conflict handling remain in Files.
- Extend the target tree with the configured music destination only under videos. Refresh it on setting/rule changes. Clear stale music Check status when folder, extensions, threshold, or rules change.
- Older saved layouts should retain their existing docks while the new dock gets its default placement through the normal Qt state lifecycle. Test this rather than adding a general migration framework.

## Effort 3: executable music rule

Add internal rule id `music_videos`, label **Move videos containing music**, media type video and rule type file. Assign one permanent unused letter-number display identifier using the existing convention. Support toggle, reordering, Check, Run Once, and Execute rules. Add it once to stored rule lists following the app's established new-rule insertion pattern; preserve existing order and toggles.

Use the same source scope as Landscape: matching files directly in the configured video directory, not photos, input-root files, or arbitrary nested directories. For a positive result, move to `<video folder>/<musicVideoFolder>/<filename>`. Use the existing conflict option: skip a conflict or enumerate `_1`, `_2`, etc.; never overwrite. Only move after successful complete analysis.

Order has a visible consequence: Landscape and Music compete for direct video-folder files. The first matching rule moves a file out of the later rule's scope. To prioritize music, collect videos first, then Music, then Landscape. Do not silently introduce recursion or nested combined categories. Explain and test both orders, and keep the preview consistent with that scope.

Music Check performs the same real analysis on eligible source files without moving them. BAD means a positive file remains eligible to move; OK means no such work remains. Do not copy the inspected Landscape check implementation's destination-first/first-file shortcut; the current README and code were not aligned on that behavior. Recheck the final committed implementation before integrating. Dependency and decode failures retain the existing failed-worker status, never OK.

Thread the music folder, threshold, model location, and FFmpeg location through the current Controller/worker/check interfaces. Update all actual call sites, including packaging smoke tests. Keep existing unrelated rule behavior intact.

## Required evidence and execution order

After the other changes are committed, establish the detector first in an isolated qualification environment. Acquire the real model, install the exact Windows dependencies, decode real licensed music/speech/noise videos with the existing FFmpeg, and invoke the SavedModel. Inspect its actual callable outputs and class-map asset. Do this before building UI around it.

Acquire and prepare the evaluation assets as implementation work; do not ask the user to supply the missing core. MUSAN provides a documented bootstrap source for music, speech, and noise. Preserve source licenses and group provenance. Add independently annotated real mixtures and difficult examples; synthetic signals and generated mixtures alone do not validate real-world music detection.

Use separate source groups for threshold selection and held-out evaluation. Measure file-level precision, recall, false-positive rate and counts, with uncertainty and duration/channel breakdowns. Include quiet background music, speech over music, a cappella, humming, ambient music, short jingles, speech, engines, applause, alarms, and long negative recordings. The raw plan's 95% recall / 1% false-positive targets remain proposed release gates, not promised pretrained-model capabilities. If measured performance fails, the feature is not complete; report the evidence instead of shipping a placeholder or silently substituting a detector.

Then integrate in these reviewable increments, with the entire feature required before declaring completion:

1. Qualified real model/decoder integration, dependency lock, model setup delivery, and measured detection report.
2. Music folder setting, Audio dock, persistence, layout, preview, and worker settings transport.
3. Rule execution/checks and actual file moves, followed by installer and UI end-to-end acceptance.

Required tests:

- Real model + real FFmpeg + real licensed audio in actual videos; no mocked detector in acceptance tests.
- Music only at EOF, short inputs, channel cancellation, music in one channel, multiple audio streams, and videos without audio.
- Chunked/whole-model prediction parity, no missed or duplicated evidence at boundaries, and bounded memory on long recordings.
- Positive moves and negative stays, custom destination, video extension selection, photos untouched, nonrecursive scan, conflicts, repeat execution, and both Landscape/Music orders.
- Read-only Check, Run Once, Execute rules, pause/stop, persisted threshold/folder, View toggle, Reset Layout, restart, and existing-layout upgrade.
- Clean Windows setup with no preinstalled app dependencies or model cache; actual installed GUI rule execution on positive and negative videos; then repeat with networking unavailable after setup.
- Reinstall/upgrade/uninstall, native dependency failures surfacing, and installer payload inspection proving no TensorFlow binaries or model weights were embedded.

Expected touch points: `folderconformer/music.py`, `pipeline.py`, `app.py`, `qml/Main.qml`, `qml/RulesPanel.qml`, target-preview construction, `pyproject.toml`, `uv.lock`, `packaging/installer.iss`, `install_runtime.py`, preparation tooling, `packaging/smoke.py`, focused tests, README, and CHANGELOG. No source implementation, dependency install, app commit, or release was performed during this review.

## Primary sources

- [Official YAMNet tutorial and pretrained model](https://www.tensorflow.org/hub/tutorials/yamnet)
- [YAMNet source and architecture](https://github.com/tensorflow/models/tree/master/research/audioset/yamnet)
- [Class map](https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv)
- [Model-owned feature extraction and padding](https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/features.py)
- [Model timing parameters](https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/params.py)
- [SavedModel local loading](https://www.tensorflow.org/api_docs/python/tf/saved_model/load)
- [TensorFlow Windows installation and prerequisites](https://www.tensorflow.org/install/pip)
- [MUSAN corpus](https://www.openslr.org/17/)
