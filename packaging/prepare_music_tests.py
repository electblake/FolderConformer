import json
from pathlib import Path
from urllib.request import urlretrieve


root = Path(__file__).resolve().parent.parent
directory = root / "build/music/fixtures"
directory.mkdir(parents=True, exist_ok=True)
for fixture in json.loads((root / "tests/music-fixtures.json").read_text(encoding="utf-8")):
    urlretrieve(fixture["url"], directory / (fixture["id"] + ".ogg"))
print(f"Downloaded licensed music evaluation recordings: {directory}")
