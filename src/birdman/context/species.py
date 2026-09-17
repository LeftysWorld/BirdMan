"""What BirdNET is allowed to report: the species plausible for this place and week, and
the list of things that are not birds at all."""
from birdman.config import LAT, LON, WEEK, SPECIES_LIST
from birdman.models.birdnet import BirdNet

GEO_MIN = 0.03              # geo-model likelihood a species needs to make the local list

NON_BIRD = {"Katydid", "Cricket", "Cicada", "Frog", "Toad", "Treefrog", "Squirrel",
            "Coyote", "Dog", "Engine", "Siren", "Human", "Noise", "Gun", "Fireworks",
            "Power tools"}


def is_bird(name: str) -> bool:
    return not any(tok.lower() in name.lower() for tok in NON_BIRD)


def local_species_file() -> str:
    """Path to the local species list, building it on first use. Delete the file after
    changing LAT, LON or WEEK so it is rebuilt."""
    if not SPECIES_LIST.exists():
        likely = BirdNet().predict_location(LAT, LON, WEEK)
        with open(SPECIES_LIST, "w") as out:
            for p in likely:
                if p.confidence >= GEO_MIN:
                    out.write(p.label + "\n")
    return str(SPECIES_LIST)
