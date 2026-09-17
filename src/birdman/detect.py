import csv, io, os, tempfile
from contextlib import redirect_stdout, redirect_stderr
from functools import lru_cache
from pathlib import Path
import birdnet

from birdman.config import LAT, LON, WEEK, MIN_CONF, CLIPS, SPECIES_LIST

AUDIO_EXT = {".wav", ".mp3", ".flac", ".ogg"}

NON_BIRD = {"Katydid", "Cricket", "Cicada", "Frog", "Toad", "Treefrog", "Squirrel",
            "Coyote", "Dog", "Engine", "Siren", "Human", "Noise", "Gun", "Fireworks",
            "Power tools"}

def is_bird(name: str) -> bool:
    return not any(tok.lower() in name.lower() for tok in NON_BIRD)

def _rows(predictions) -> list[dict]:
    """birdnet only exports to a file, so round-trip through a private temp file."""
    fd, tmp = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            predictions.to_csv(tmp)
        with open(tmp) as f:
            return list(csv.DictReader(f))
    finally:
        os.unlink(tmp)

def local_species_file() -> str:
    if not SPECIES_LIST.exists():
        geo = birdnet.load("geo", "2.4", "tf", library="litert")
        with open(SPECIES_LIST, "w") as out:
            for row in _rows(geo.predict(LAT, LON, week=WEEK)):
                if float(row["confidence"]) >= 0.03:
                    out.write(row["species_name"] + "\n")
    return str(SPECIES_LIST)

@lru_cache(maxsize=1)
def _model():
    """Loaded once per process - the watcher analyses many clips with the same model."""
    return birdnet.load("acoustic", "2.4", "tf", library="litert")

def detect_clip(clip: Path) -> dict[str, float]:
    """Birds heard in one recording: {common name: best confidence}, above MIN_CONF only."""
    rows = _rows(_model().predict(str(clip), custom_species_list=local_species_file()))
    found: dict[str, float] = {}
    best = ("", 0.0)
    for row in rows:
        conf = float(row["confidence"])
        common = row["species_name"].split("_", 1)[1]
        if conf > best[1]:
            best = (common, conf)
        if conf >= MIN_CONF and is_bird(common):
            found[common] = max(conf, found.get(common, 0.0))
    print(f"{Path(clip).name}: {sorted(found)}   best: {best[0]} ({best[1]:.2f})")
    return found

def detect_species() -> list[str]:
    """One-shot: every clip in clips/, most confident species first (used by main.py)."""
    species: dict[str, float] = {}
    for clip in sorted(CLIPS.glob("*")):
        if clip.suffix.lower() in AUDIO_EXT:
            for name, conf in detect_clip(clip).items():
                species[name] = max(conf, species.get(name, 0.0))
    return sorted(species, key=species.get, reverse=True)
