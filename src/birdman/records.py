"""The data that travels between parts of BirdMan. One place to see, and to change, what a
detection or a heard species actually is.

Plain data only: fields and small conveniences, no pipeline logic.

(Deliberately not called types.py - that would shadow Python's own `types` module for any
script run from inside this folder.)
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Prediction:
    """One raw line of model output, before any threshold or filter is applied."""
    label: str                  # BirdNET's own label: "Scientific name_Common Name"
    confidence: float

    @property
    def common(self) -> str:
        return self.label.split("_", 1)[1] if "_" in self.label else self.label

    @property
    def scientific(self) -> str:
        return self.label.split("_", 1)[0]


@dataclass(frozen=True)
class Detection:
    """A bird accepted as heard in one recording."""
    species: str                # common name
    confidence: float


@dataclass
class SpeciesRecord:
    """One species in today's list."""
    species: str
    first_heard: datetime
    last_heard: datetime
    best_confidence: float
    count: int = 1

    def heard_again(self, when: datetime, confidence: float) -> None:
        self.last_heard = when
        self.best_confidence = max(self.best_confidence, confidence)
        self.count += 1

    # heard.json keeps the short keys it has always had, so existing files still load.
    def to_json(self) -> dict:
        return {"first": self.first_heard.isoformat(timespec="seconds"),
                "last": self.last_heard.isoformat(timespec="seconds"),
                "conf": self.best_confidence,
                "count": self.count}

    @classmethod
    def from_json(cls, species: str, d: dict) -> "SpeciesRecord":
        return cls(species=species,
                   first_heard=datetime.fromisoformat(d["first"]),
                   last_heard=datetime.fromisoformat(d["last"]),
                   best_confidence=float(d["conf"]),
                   count=int(d["count"]))
