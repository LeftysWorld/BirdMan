import sys
from birdman.config import OUT, DEMO_BIRDS
from birdman.steps.collage import build_collage
from birdman.steps.eink import render

PREVIEW = OUT.with_name(OUT.stem + "_preview.png")

def main():
    if "--demo" in sys.argv:
        names = DEMO_BIRDS
    else:
        from birdman.steps.detect import detect_species
        names = detect_species()
    if not names:
        sys.exit("no detections above threshold")
    artwork, text = build_collage(names)
    device, preview = render(artwork, text)
    device.save(OUT)            # pure primaries: send this one to the Inky
    preview.save(PREVIEW)       # what it should look like on the wall
    print(f"wrote {OUT} and {PREVIEW} with {len(names)} species: {names}")


if __name__ == "__main__":
    main()
