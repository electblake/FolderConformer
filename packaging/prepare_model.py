import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlretrieve

from folderconformer.music_model import MODEL_PATH, MODEL_URL


MODEL_PATH.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as directory:
    archive = Path(directory) / "yamnet.tar.gz"
    urlretrieve(MODEL_URL, archive)
    with tarfile.open(archive) as model:
        model.extractall(MODEL_PATH, filter="data")
print(f"Installed YAMNet 1: {MODEL_PATH}")
