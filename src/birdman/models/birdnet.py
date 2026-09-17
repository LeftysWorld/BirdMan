"""BirdNET: loading the two models and running them. Nothing here knows about thresholds,
filters or what the results are used for."""
import csv, io, os, tempfile
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import birdnet as _birdnet                      # the library; this module shares its name

from birdman.records import Prediction


class BirdNet:
    """The BirdNET models. Creating one is free; the acoustic model loads the first time
    it is needed and is then kept for the life of the object."""

    VERSION = "2.4"

    def __init__(self):
        self._acoustic = None

    def predict_clip(self, clip: Path, species_list: str) -> list[Prediction]:
        """Every species the acoustic model reports for one recording, limited to the
        labels in `species_list` (path to a text file)."""
        if self._acoustic is None:
            self._acoustic = _birdnet.load("acoustic", self.VERSION, "tf", library="litert")
        return self._read(self._acoustic.predict(str(clip), custom_species_list=species_list))

    def predict_location(self, lat: float, lon: float, week: int) -> list[Prediction]:
        """How likely each species is at this place and week. The geo model is only needed
        when the local species list is rebuilt, so it is loaded on demand and not kept."""
        geo = _birdnet.load("geo", self.VERSION, "tf", library="litert")
        return self._read(geo.predict(lat, lon, week=week))

    @staticmethod
    def _read(predictions) -> list[Prediction]:
        """birdnet only exports to a file, so round-trip through a private temp file."""
        fd, tmp = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                predictions.to_csv(tmp)
            with open(tmp) as f:
                return [Prediction(row["species_name"], float(row["confidence"]))
                        for row in csv.DictReader(f)]
        finally:
            os.unlink(tmp)
