"""Today's list of heard species, kept on disk so a restart or reboot loses nothing."""
import json
from birdman.clock import now, today
from birdman.config import STATE

FILE = STATE / "heard.json"


class Heard:
    def __init__(self, fresh: bool = False):
        self.day = today()
        self.species: dict[str, dict] = {}
        if not fresh and FILE.exists():
            try:
                data = json.loads(FILE.read_text())
                if data["day"] == self.day:             # yesterday's list is simply dropped
                    self.species = dict(data["species"])
            except (ValueError, KeyError, TypeError):   # power cut mid-write, hand edits...
                bad = FILE.with_name("heard.corrupt.json")
                FILE.replace(bad)
                print(f"state file was unreadable - starting the day fresh (kept as {bad.name})")
        self._save()

    def roll_over(self) -> bool:
        """Call this often. True exactly once, when the date has changed: the list is now empty."""
        if today() == self.day:
            return False
        self.day, self.species = today(), {}
        self._save()
        return True

    def add(self, found: dict[str, float]) -> list[str]:
        """Record one clip's detections. Returns the species that are new today."""
        self.roll_over()
        stamp = now().isoformat(timespec="seconds")
        new = []
        for name, conf in found.items():
            s = self.species.get(name)
            if s is None:
                self.species[name] = {"first": stamp, "last": stamp, "conf": conf, "count": 1}
                new.append(name)
            else:
                s.update(last=stamp, conf=max(conf, s["conf"]), count=s["count"] + 1)
        self._save()
        return new

    def names(self) -> list[str]:
        """Arrival order: the first bird of the day is the hero, later birds join the flock."""
        return sorted(self.species, key=lambda n: self.species[n]["first"])

    def _save(self):
        tmp = FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"day": self.day, "species": self.species}, indent=2))
        tmp.replace(FILE)
