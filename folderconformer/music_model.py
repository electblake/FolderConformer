import sys
from pathlib import Path


MODEL_VERSION = "YAMNet 1"
MODEL_URL = "https://www.kaggle.com/api/v1/models/google/yamnet/tensorFlow2/yamnet/1/download"
MODEL_SHA256 = "b80da2a1a56926fb0767205051a200dd7b3beaf3ea1ea126c42a53943996e5e0"
MODEL_PATH = Path(sys.prefix) / "models/yamnet/1"
MUSIC_THRESHOLD = 0.504

DEFAULT_AUDIO_CLASSES = (("/m/04rlf", MUSIC_THRESHOLD), ("/m/015lz1", MUSIC_THRESHOLD),
                         ("/m/02fxyj", MUSIC_THRESHOLD))
