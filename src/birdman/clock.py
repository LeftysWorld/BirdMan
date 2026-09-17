"""The project's one clock. Everything that cares what day it is asks here.

Normally this is just the real time. To rehearse midnight without staying up for it:

    BIRDMAN_NOW="2026-09-17 23:59:30" uv run watch.py --fresh

The clock starts at that moment and ticks forward normally, so 30 seconds later it is
tomorrow and you can watch the frame reset.
"""
import os
from datetime import datetime, timedelta

_offset = None


def now() -> datetime:
    global _offset
    if _offset is None:
        fake = os.environ.get("BIRDMAN_NOW")
        _offset = datetime.fromisoformat(fake) - datetime.now() if fake else timedelta(0)
    return datetime.now() + _offset


def today() -> str:
    return now().strftime("%Y-%m-%d")
