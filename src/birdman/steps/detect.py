"""Step: recording -> birds heard in it."""
from pathlib import Path

from birdman.config import MIN_CONF, CLIPS
from birdman.context.species import is_bird, local_species_file
from birdman.models.birdnet import BirdNet
from birdman.records import Detection

AUDIO_EXT = {".wav", ".mp3", ".flac", ".ogg"}

_birdnet = BirdNet()        # one per process: the watcher reuses the loaded model for every clip


def detect_clip(clip: Path) -> list[Detection]:
    """Birds heard in one recording: one Detection per species, at its best confidence,
    keeping only birds at or above MIN_CONF."""
    best_by_species: dict[str, float] = {}
    top = None
    for p in _birdnet.predict_clip(clip, local_species_file()):
        if top is None or p.confidence > top.confidence:
            top = p
        if p.confidence >= MIN_CONF and is_bird(p.common):
            best_by_species[p.common] = max(p.confidence, best_by_species.get(p.common, 0.0))
    guess = f"{top.common} ({top.confidence:.2f})" if top else "nothing"
    print(f"{Path(clip).name}: {sorted(best_by_species)}   best: {guess}")
    return [Detection(species, conf) for species, conf in best_by_species.items()]


def detect_species() -> list[str]:
    """One-shot: every clip in dev/clips/, most confident species first (used by render_once)."""
    best: dict[str, float] = {}
    for clip in sorted(CLIPS.glob("*")):
        if clip.suffix.lower() in AUDIO_EXT:
            for d in detect_clip(clip):
                best[d.species] = max(d.confidence, best.get(d.species, 0.0))
    return sorted(best, key=best.get, reverse=True)
