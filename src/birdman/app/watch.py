"""The always-on half: analyse every recording that lands in inbox/, update the frame.

    uv run birdman-watch --fresh                    # testing: start empty, redraw instantly
    uv run birdman-watch --settle 30 --min-gap 180        # on the real panel

It does not care where recordings come from. Today simulate.py drops xeno-canto clips into
inbox/; later the microphone recorder writes there instead and nothing here changes.
"""
import argparse
import time

from birdman.steps.illustrate import art_path
from birdman.clock import now
from birdman.config import INBOX, HISTORY, OUT
from birdman.steps.detect import detect_clip, AUDIO_EXT
from birdman.state import Heard
from birdman.steps.collage import build_collage, MAX_BIRDS
from birdman.steps.eink import render
from birdman.steps.panel import push_to_panel

PREVIEW = OUT.with_name(OUT.stem + "_preview.png")
LIVE = OUT.with_name("live.html")
FILE_SETTLE = 3             # s a recording must sit untouched before we read it
ART_RETRY = 600             # s before retrying artwork that failed to generate
KEEP_SNAPSHOTS = 500


def redraw(heard: Heard) -> list[str]:
    """Draw and publish the frame. Returns species that are still waiting for artwork."""
    names = heard.names()
    artwork, text = build_collage(names)
    device, preview = render(artwork, text)
    device.save(OUT)
    preview.save(PREVIEW)
    snap = HISTORY / f"{now():%Y%m%d_%H%M%S}_{len(names):02d}_species.png"
    preview.save(snap)
    for old in sorted(HISTORY.glob("*.png"))[:-KEEP_SNAPSHOTS]:
        old.unlink(missing_ok=True)
    waiting = [n for n in names[:MAX_BIRDS] if not art_path(n).exists()]
    note = f", no artwork yet for {waiting} (retry in {ART_RETRY // 60} min)" if waiting else ""
    print(f"  -> {len(names)} species on the frame, {push_to_panel(device)}, {snap.name}{note}")
    return waiting


def write_live_page() -> None:
    """Open live.html in a browser to watch the frame change without touching anything."""
    LIVE.write_text(
        "<body style='margin:0;background:#777;display:grid;place-items:center;height:100vh'>"
        f"<img id=f src='{PREVIEW.name}' style='max-width:95vw;max-height:95vh;"
        "box-shadow:0 10px 40px #0008'>"
        f"<script>setInterval(()=>f.src='{PREVIEW.name}?'+Date.now(),2000)</script>"
    )


def pending():
    """Recordings that are finished being written, oldest first."""
    cutoff = time.time() - FILE_SETTLE
    clips = []
    for p in INBOX.iterdir():
        if p.suffix.lower() not in AUDIO_EXT or p.name.startswith("."):
            continue
        try:
            st = p.stat()
        except FileNotFoundError:
            continue
        if st.st_size > 0 and st.st_mtime <= cutoff:    # a recorder may still be writing newer ones
            clips.append((st.st_mtime, p))
    return [p for _, p in sorted(clips)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true", help="forget what was heard earlier today")
    ap.add_argument("--settle", type=int, default=0,
                    help="after a new species, wait this many seconds for others before "
                         "redrawing, so a dawn chorus becomes one update (try 30)")
    ap.add_argument("--min-gap", type=int, default=0,
                    help="never redraw more often than this many seconds (try 180 on the panel)")
    args = ap.parse_args()

    heard = Heard(fresh=args.fresh)
    write_live_page()
    print(f"watching {INBOX}/ - {len(heard.names())} species so far today. Ctrl-C to stop.")

    dirty_since = time.time() - args.settle     # draw right away: today's flock, or the quiet plate
    last_draw = 0.0
    retry_at = None

    while True:
        if heard.roll_over():
            print(f"--- new day: {heard.day} ---")
            dirty_since, retry_at = time.time() - args.settle, None     # reset the wall promptly

        for clip in pending():
            try:
                new = heard.add(detect_clip(clip))
            except Exception as e:
                print(f"  could not analyse {clip.name}: {e}")
                new = []
            clip.unlink(missing_ok=True)        # inbox holds copies; the originals stay in clips/
            if new:
                print(f"  NEW today: {', '.join(new)}")
                dirty_since = dirty_since or time.time()

        t = time.time()
        if retry_at and t >= retry_at:
            dirty_since, retry_at = dirty_since or t - args.settle, None
        if dirty_since and t - dirty_since >= args.settle and t - last_draw >= args.min_gap:
            try:
                waiting = redraw(heard)
                retry_at = time.time() + ART_RETRY if waiting else None
            except Exception as e:
                print(f"  redraw failed: {e.__class__.__name__}: {e}")
                retry_at = time.time() + ART_RETRY
            dirty_since, last_draw = None, time.time()
        time.sleep(1)


if __name__ == "__main__":
    main()
