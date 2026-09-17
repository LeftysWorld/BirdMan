"""Today's list of heard species, kept on disk so a restart or reboot loses nothing."""
import json

from birdman.clock import now, today
from birdman.config import STATE
from birdman.records import Detection, SpeciesRecord

FILE = STATE / "heard.json"


class Heard:
    def __init__(self, fresh: bool = False):
        self.day = today()
        self.species: dict[str, SpeciesRecord] = {}
        if not fresh and FILE.exists():
            try:
                data = json.loads(FILE.read_text())
                if data["day"] == self.day:             # yesterday's list is simply dropped
                    self.species = {name: SpeciesRecord.from_json(name, d)
                                    for name, d in data["species"].items()}
            except (ValueError, KeyError, TypeError, AttributeError):   # power cut mid-write, hand edits...
                bad = FILE.with_name("heard.corrupt.json")
                FILE.replace(bad)
                self.species = {}
                print(f"state file was unreadable - starting the day fresh (kept as {bad.name})")
        self._save()

    def roll_over(self) -> bool:
        """Call this often. True exactly once, when the date has changed: the list is now empty."""
        if today() == self.day:
            return False
        self.day, self.species = today(), {}
        self._save()
        return True

    def add(self, detections: list[Detection]) -> list[str]:
        """Record one clip's detections. Returns the species that are new today."""
        self.roll_over()
        when = now().replace(microsecond=0)
        new = []
        for d in detections:
            record = self.species.get(d.species)
            if record is None:
                self.species[d.species] = SpeciesRecord(d.species, when, when, d.confidence)
                new.append(d.species)
            else:
                record.heard_again(when, d.confidence)
        self._save()
        return new

    def names(self) -> list[str]:
        """Arrival order: the first bird of the day is the hero, later birds join the flock."""
        return sorted(self.species, key=lambda n: self.species[n].first_heard)

    def _save(self):
        tmp = FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(
            {"day": self.day, "species": {n: r.to_json() for n, r in self.species.items()}},
            indent=2))
        tmp.replace(FILE)
