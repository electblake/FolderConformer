# Music detection implementation evidence

2026-10-23. Windows x64, managed CPython 3.12.10, TensorFlow 2.21.0, Google YAMNet v1. The classifier is the actual downloaded SavedModel, not a test double or newly trained estimator.

## Model and operating point

Setup uses the public versioned Kaggle download with SHA-256 `b80da2a1a56926fb0767205051a200dd7b3beaf3ea1ea126c42a53943996e5e0`. The archive is 14,242,921 bytes compressed and 18,275,381 bytes extracted. It contains the SavedModel, variables, and class map. Inference loads only the installed local directory.

The decision uses the maximum Music, Singing, or Humming score across audio streams, channels, and time. Speech is not a veto. Threshold selection used four complete recordings: Vibe Ace and Sweet Waltz (positive), LibriSpeech 5703-47212-0000 and a robin recording (negative). Negative maximum: 0.008343; positive minimum: 0.998842. The midpoint rounded upward to three decimals is **0.504**. This small-set operating point is editable in Audio and is not calibrated file confidence.

## Real-recording evaluation

The separate recording set produced these initial results after actual AAC video encoding and FFmpeg decoding:

| Recording | Label | Maximum selected score | Result at 0.504 |
|---|---|---:|---|
| Choice, drum and bass | music | 0.998538 | positive |
| Dance of the Sugar Plum Fairy | music | 0.999278 | positive |
| Solo trumpet | music | 0.983552 | positive |
| Hungarian Dance No. 5 | music | 0.999458 | positive |
| LibriSpeech 3436-172162-0000 | no music | 0.000886 | negative |
| LibriSpeech 198-209-0000 | no music | 0.007579 | negative |
| Glacier Bay humpback whales | no music | 0.597090 | **false positive** |

Counts: TP 4, FN 0, TN 2, FP 1. Sample precision 80%, recall 100%, F1 88.9%, false-positive rate 33.3%. These tiny samples do not estimate deployment accuracy. The same performer appears in one calibration and one separate recording, so this is not an artist-disjoint benchmark. Unknown overlap with YAMNet's original AudioSet training data is another limitation. No threshold was retuned against these seven results.

The initial four-recording pass took 2.1 seconds and the seven-recording pass 4.2 seconds after model construction on the development machine, including encoding, probing, and inference. These are local observations, not hardware-independent performance claims. Streaming parity corrections were subsequently covered by the regression suite.

The proposed 95% recall / 1% false-positive release-quality target is **not established or met by this evidence**. Whale-like tonal sounds are a demonstrated limitation. Broader independent annotations are still required to establish that quality level, including real background music, a cappella, humming, quiet music, environmental sounds, long negatives, and short passages. The feature is implemented and can classify and move real videos; it must not be described as meeting that unproven accuracy target.

## Functional verification

The real-model tests cover actual positive/negative videos, no audio, music only at the end, music under speech, multiple audio tracks, music in one channel, opposite-polarity stereo, custom destinations, conflict skipping/numbering, repeat execution, nonrecursive scope, photos left untouched, read-only checks, Landscape/Music order, and stopping before the current file moves.

The stream test compares selected scores against whole-waveform SavedModel inference at short lengths, exact context and hop boundaries, and multi-block lengths. Tolerance: absolute 0.00002 plus relative 0.0001. The exported graph sometimes creates an extra padded prediction at exact float-rounding boundaries. The app takes only complete contexts inside a block and the final context needed to cover the real tail; the model still performs all feature extraction and padding. This prevents internal padding from creating false evidence or duplicate trailing contexts.

Fixtures are downloaded explicitly by preparation tooling; their published hashes are checked by tests. Audio is not bundled in the installer. Source and license attribution: [fixture manifest](../tests/music-fixtures.json).

Run logs, generated videos, model qualification results, and GUI evidence are under `build/`. Installer verification is performed by `packaging/smoke.py`, using the installed interpreter and model, dead HTTP proxies for inference, real GUI Check/Run Once/Execute actions, reinstall, and uninstall. No credential is passed to that public model download.

### Online installer acceptance

The 2,741,056-byte Setup executable passed installation into a fresh private runtime with a fresh managed-Python/bootstrap cache, real setup-time YAMNet inference, installed GUI Check/Run Once/Execute and pause/stop/cancel, all 13 real-model integration tests with dead HTTP proxies, reinstall, and uninstall. This was run on the development Windows machine, not a clean Windows VM. The machine-wide Microsoft runtime update requested a restart on its first installation; the subsequent successful setup reported no restart needed.

The first acceptance run caught an archive-layout defect: Inno extracted the gzip layer but left a tar file. Setup now downloads and verifies the compressed archive and Python's standard tarfile module extracts its contents into the private venv before model verification. The original installed app runtime, uninstall registration, and shortcuts were restored after testing.

### Repository regressions

The combined workspace suite passed **131 tests** in 126.026 seconds after the concurrently developed media-folder rules and their tests were included. Earlier runs exposed an intermittent native Qt exit crash during a floating-dock close/restart case and tests running against changing rule lists; the final full run passed those cases. The native crash was not independently root-caused, so this result is not a claim that such crashes are impossible.

The final rebuilt installer repeated the complete acceptance run successfully after the media-folder changes were committed. Logs: `build/combined-regression.log` and `build/final-installer-smoke.log`. Native dock and embedded QML captures are `build/music/installed-ui.png` and `build/music/installed-rules.png`.

### Early positive exit

Music analysis now returns positive after the first batch with a selected class score at or above the threshold. The decoder is terminated and remaining tracks are skipped. Negative results still require a complete scan. Reported maximum scores and evidence cover only the analyzed prefix; the historical whole-recording scores above describe the original full-scan evaluation.

Validation: all 15 real-model tests passed, including early decoder termination on a two-minute/two-track video, threshold equality, full negative scans, and late music. The source GUI smoke test also passed Check, Run Once, Execute, conflicts, and pause/stop/cancel.
