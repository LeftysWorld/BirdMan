import csv, os, sys
from pathlib import Path
from datetime import datetime

import numpy as np
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import birdnet
from google import genai
from google.genai import types

load_dotenv()

LAT, LON, WEEK = 33.69, -78.89, 38      # Myrtle Beach, mid-Sept
MIN_CONF = 0.7
CLIPS, CACHE, OUT = Path("clips"), Path("cache"), Path("../frame.png")
W, H = 800, 480                         # Inky Impression 7.3"
CACHE.mkdir(exist_ok=True)

FONT_REG = "fonts/CormorantGaramond-VariableFont_wght.ttf"
FONT_ITA = "fonts/CormorantGaramond-Italic-VariableFont_wght.ttf"

NON_BIRD = {"Katydid", "Cricket", "Cicada", "Frog", "Toad", "Treefrog", "Squirrel",
            "Coyote", "Dog", "Engine", "Siren", "Human", "Noise", "Gun", "Fireworks",
            "Power tools"}

def is_bird(name: str) -> bool:
    return not any(tok.lower() in name.lower() for tok in NON_BIRD)

# ---------- 1. BirdNET ----------
def local_species_file() -> str:
    path = Path("../local_species.txt")
    if not path.exists():
        geo = birdnet.load("geo", "2.4", "tf", library="litert")
        geo.predict(LAT, LON, week=WEEK).to_csv("geo.csv")
        with open("geo.csv") as f, open(path, "w") as out:
            for row in csv.DictReader(f):
                if float(row["confidence"]) >= 0.03:
                    out.write(row["species_name"] + "\n")
    return str(path)

def detect_species() -> list[str]:
    model = birdnet.load("acoustic", "2.4", "tf", library="litert")
    species_list = local_species_file()
    species: dict[str, float] = {}
    for clip in sorted(CLIPS.glob("*")):
        if clip.suffix.lower() not in {".wav", ".mp3", ".flac", ".ogg"}:
            continue
        model.predict(str(clip), custom_species_list=species_list).to_csv("tmp.csv")
        found = set()
        with open("tmp.csv") as f:
            for row in csv.DictReader(f):
                conf = float(row["confidence"])
                common = row["species_name"].split("_", 1)[1]
                if conf >= MIN_CONF and is_bird(common):
                    species[common] = max(conf, species.get(common, 0))
                    found.add(common)
        print(f"{clip.name}: {sorted(found)}")
    return sorted(species, key=species.get, reverse=True)

# ---------- 2. Gemini ----------
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

def prompt_for(name: str) -> str:
    return (
        f"A single {name}, full body, in the style of a Japanese ukiyo-e woodblock print "
        "by Hiroshige. Flat areas of color, bold black keyline outlines, subtle woodgrain "
        "texture inside the color areas. Limited ink palette: red, blue, yellow, green, black. "
        "The bird is completely isolated on a plain pure white background. "
        "No branch, no foliage, no ground, no shadow, no border, no frame, no text. "
        "The bird fills most of the square canvas."
    )

def bird_image(name: str) -> Image.Image:
    path = CACHE / f"{name.replace(' ', '_')}.png"
    if path.exists():
        return Image.open(path)
    try:
        resp = client.models.generate_content(
            model="gemini-3.1-flash-image",
            contents=prompt_for(name),
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        for part in resp.candidates[0].content.parts:
            if part.inline_data:
                path.write_bytes(part.inline_data.data)
                print(f"generated {name}")
                return Image.open(path)
    except Exception as e:
        print(f"gemini failed for {name}: {e.__class__.__name__}")
    ph = Image.new("RGB", (400, 400), (200, 60, 40))
    ImageDraw.Draw(ph).text((20, 190), name, fill="white")
    return ph

def cutout(img: Image.Image) -> Image.Image:
    """Make near-white pixels transparent so birds overlap cleanly."""
    a = np.array(img.convert("RGBA"))
    a[a[..., :3].min(axis=2) > 232, 3] = 0
    out = Image.fromarray(a)
    out.putalpha(out.getchannel("A").filter(ImageFilter.GaussianBlur(0.8)))
    return out

# ---------- 3. Collage ----------
SLOTS = [  # (cx, cy, size, rotation) — big anchor first, supporting birds after
    (300, 300, 300, -6),
    (585, 285, 250,  5),
    (105, 330, 210,  7),
    (735, 400, 190, -8),
    (445, 420, 170,  9),
    (200, 445, 150, -5),
    (640, 455, 140,  6),
    (60,  455, 120,  4),
]

def font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()

def build_collage(names: list[str]) -> Image.Image:
    canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    title_f, sub_f, label_f = font(FONT_REG, 46), font(FONT_ITA, 20), font(FONT_REG, 17)
    title = "Birds Visited Today"
    draw.text(((W - draw.textlength(title, font=title_f)) / 2, 22), title, fill="black", font=title_f)
    sub = f"{datetime.now():%A, %B %-d}  ·  {len(names)} species"
    draw.text(((W - draw.textlength(sub, font=sub_f)) / 2, 76), sub, fill="black", font=sub_f)
    draw.line([(W/2 - 60, 108), (W/2 + 60, 108)], fill="black", width=1)

    n = min(len(names), len(SLOTS))
    scale = 1.0 + (8 - n) * 0.05
    for name, (cx, cy, size, rot) in zip(names[:n], SLOTS):
        size = int(size * scale)
        bird = cutout(bird_image(name))
        bird.thumbnail((size, size), Image.LANCZOS)
        bird = bird.rotate(rot, expand=True, resample=Image.BICUBIC)
        x, y = cx - bird.width // 2, cy - bird.height // 2
        canvas.alpha_composite(bird, (x, y))
        lw = draw.textlength(name, font=label_f)
        draw.text((cx - lw / 2, y + bird.height - 14), name, fill="black", font=label_f)

    return canvas.convert("RGB")

# ---------- 4. Spectra 6 ----------
def to_spectra6(img: Image.Image) -> Image.Image:
    pal = Image.new("P", (1, 1))
    pal.putpalette([0,0,0, 255,255,255, 255,0,0, 0,255,0, 0,0,255, 255,255,0] + [0]*750)
    return img.quantize(palette=pal, dither=Image.FLOYDSTEINBERG).convert("RGB")

# ---------- main ----------
if __name__ == "__main__":
    names = detect_species()
    if not names:
        sys.exit("no detections above threshold")
    to_spectra6(build_collage(names)).save(OUT)
    print(f"wrote {OUT} with {len(names)} species: {names}")
