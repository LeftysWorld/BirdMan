"""Pretend to be the microphone: drop clips from clips/ into inbox/ one at a time.

    uv run dev/simulate.py                    # one clip every 20 s, in filename order
    uv run dev/simulate.py --every 5 --shuffle
    uv run dev/simulate.py --rounds 3         # play the library three times (repeats = no redraw)
"""
import argparse
import random
import shutil
import time

from birdman.config import CLIPS, INBOX

AUDIO_EXT = {".wav", ".mp3", ".flac", ".ogg"}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=float, default=20, help="seconds between clips")
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--rounds", type=int, default=1)
    args = ap.parse_args()

    clips = sorted(p for p in CLIPS.iterdir() if p.suffix.lower() in AUDIO_EXT)
    if not clips:
        raise SystemExit(f"no audio files in {CLIPS}/")

    for rnd in range(args.rounds):
        order = random.sample(clips, len(clips)) if args.shuffle else clips
        for i, clip in enumerate(order, 1):
            # copy under a hidden name, then rename: the watcher never sees a half-written file
            tmp = INBOX / f".{clip.name}"
            shutil.copy(clip, tmp)
            tmp.rename(INBOX / f"{int(time.time())}_{clip.name}")
            print(f"[round {rnd + 1}] {i}/{len(order)}  heard: {clip.name}")
            time.sleep(args.every)
    print("done")
