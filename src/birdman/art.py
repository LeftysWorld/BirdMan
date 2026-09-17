import os
import numpy as np
from dotenv import load_dotenv
from PIL import Image, ImageFilter
from google import genai
from google.genai import types
import hashlib

from birdman.config import ART, ENV_FILE, GEMINI_MODEL

load_dotenv(ENV_FILE)
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

POSES = [
    "perched in profile",
    "in flight with wings spread",
    "hopping on the ground, body angled toward the viewer",
    "perched and looking back over its shoulder",
    "perched with its head tilted up, singing",
    "landing with wings half open and tail fanned",
    "perched, seen from a three-quarter front angle",
]

def prompt_for(name: str) -> str:
    pose = POSES[sum(map(ord, name)) % len(POSES)]
    return (
        f"A single {name}, full body, {pose}, in the style of a Japanese ukiyo-e woodblock "
        "print by Hiroshige. Flat, clean areas of color with bold black keyline outlines "
        "and generous areas of plain white paper left unprinted. Ink palette strictly: "
        "red, blue, yellow, green, and black — solid flat inks, no gradients, no shading. "
        "The bird is completely isolated on a plain pure white background. "
        "No branch, no foliage, no ground, no shadow, no border, no frame, no text. "
        "The bird fills most of the square canvas and faces to the left."
    )

def plate_image(names: list[str]) -> Image.Image:
    """One composed plate of all birds, using the per-species images as references."""
    key = hashlib.sha1("|".join(sorted(names)).encode()).hexdigest()[:12]
    path = ART / f"plate_{key}.png"
    if path.exists():
        return Image.open(path)

    refs = [img for n in names[:8] if (img := bird_image(n)) is not None]
    listing = ", ".join(names)
    prompt = (
        f"Compose a single naturalist's plate showing these {len(names)} birds together: "
        f"{listing}. Use the attached reference images for each bird's appearance and keep "
        "their style identical. Arrange them as a loose, natural flock: one bird clearly "
        "largest near the center, the others smaller at varied distances, some overlapping "
        "slightly, some perched and some in flight, facing different directions, uneven "
        "spacing like a real group of birds. Japanese ukiyo-e woodblock style: flat solid "
        "ink areas, bold black keylines, no gradients or shading. Ink palette strictly red, "
        "blue, yellow, green, black on plain white paper. Wide landscape composition with "
        "generous empty white margin on all sides. No branches, foliage, ground, shadows, "
        "border, frame, or text of any kind."
    )
    try:
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[prompt, *refs],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="21:9"),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        for part in resp.candidates[0].content.parts:
            if part.inline_data:
                path.write_bytes(part.inline_data.data)
                print(f"generated plate for {len(names)} birds")
                return Image.open(path)
    except Exception as e:
        print(f"gemini plate failed: {e.__class__.__name__}")
    return Image.new("RGB", (2100, 900), "white")

def art_path(name: str):
    return ART / f"{name.replace(' ', '_')}.png"

def bird_image(name: str) -> Image.Image | None:
    """The bird's artwork, generated on first request. None if Gemini can't be reached
    right now - nothing is cached in that case, so the next call simply tries again."""
    path = art_path(name)
    if path.exists():
        return Image.open(path)
    try:
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt_for(name),
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        for part in resp.candidates[0].content.parts:
            if part.inline_data:
                tmp = path.with_suffix(".part")
                tmp.write_bytes(part.inline_data.data)
                Image.open(tmp).verify()                # don't cache a truncated download
                tmp.replace(path)
                print(f"generated {name}")
                return Image.open(path)
        print(f"gemini returned no image for {name}")
    except Exception as e:
        print(f"gemini failed for {name}: {e.__class__.__name__}")
    return None

def cutout(img: Image.Image) -> Image.Image:
    """Trim the border, then make the *paper* transparent - whatever shade it came back as.

    Gemini doesn't always return pure white paper: some generations come back faintly
    cream or grey, with a little noise. A fixed "brighter than 232" test misses that paper,
    so the whole square stays semi-solid and the packer treats it as one huge bird. Instead
    we sample the paper colour from the image's own border and key out anything close to it.
    """
    w, h = img.size
    img = img.convert("RGB").crop((int(w * .02), int(h * .02), int(w * .98), int(h * .98)))
    rgb = np.asarray(img).astype(np.int16)

    t = max(4, min(rgb.shape[:2]) // 50)                    # border ring thickness
    ring = np.concatenate([rgb[:t].reshape(-1, 3), rgb[-t:].reshape(-1, 3),
                           rgb[:, :t].reshape(-1, 3), rgb[:, -t:].reshape(-1, 3)])
    paper = np.median(ring, axis=0)

    dist = np.abs(rgb - paper).max(axis=2)                  # how far each pixel is from paper
    ring_dist = np.abs(ring - paper).max(axis=1)
    tol = float(np.clip(np.percentile(ring_dist, 99) + 14, 24, 70))   # paper noise + headroom

    alpha = np.clip((dist - tol) / 10.0, 0, 1) * 255        # short soft ramp, no halo of paper
    if (alpha > 40).mean() < 0.01:                          # nothing left (e.g. solid placeholder)
        alpha[:] = 255

    out = img.convert("RGBA")
    out.putalpha(Image.fromarray(alpha.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)))
    return out
