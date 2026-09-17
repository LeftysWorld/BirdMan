"""Step: species -> artwork file in assets/art/. Generated once, reused forever."""
import hashlib

from PIL import Image

from birdman.config import ART
from birdman.context.prompts import prompt_for, plate_prompt
from birdman.models.gemini import GeminiImages

_gemini = GeminiImages()    # connects on first use, so importing this never needs the API key


def art_path(name: str):
    return ART / f"{name.replace(' ', '_')}.png"


def bird_image(name: str) -> Image.Image | None:
    """The bird's artwork, generated on first request. None if Gemini can't be reached
    right now - nothing is cached in that case, so the next call simply tries again."""
    path = art_path(name)
    if path.exists():
        return Image.open(path)
    try:
        data = _gemini.generate(prompt_for(name))
        if data:
            tmp = path.with_suffix(".part")
            tmp.write_bytes(data)
            Image.open(tmp).verify()                    # don't cache a truncated download
            tmp.replace(path)
            print(f"generated {name}")
            return Image.open(path)
        print(f"gemini returned no image for {name}")
    except Exception as e:
        print(f"gemini failed for {name}: {e.__class__.__name__}")
    return None


def plate_image(names: list[str]) -> Image.Image:
    """One composed plate of all birds, using the per-species images as references.
    Not used by the collage at present."""
    key = hashlib.sha1("|".join(sorted(names)).encode()).hexdigest()[:12]
    path = ART / f"plate_{key}.png"
    if path.exists():
        return Image.open(path)

    refs = [img for n in names[:8] if (img := bird_image(n)) is not None]
    try:
        data = _gemini.generate(plate_prompt(names), references=refs, aspect_ratio="21:9")
        if data:
            path.write_bytes(data)
            print(f"generated plate for {len(names)} birds")
            return Image.open(path)
    except Exception as e:
        print(f"gemini plate failed: {e.__class__.__name__}")
    return Image.new("RGB", (2100, 900), "white")
