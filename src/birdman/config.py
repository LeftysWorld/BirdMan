from pathlib import Path

# Every path hangs off the project root, so it no longer matters which directory you (or
# systemd on the Pi) launch from.   src/birdman/config.py -> parents[2] is BirdMan/
ROOT = Path(__file__).resolve().parents[2]

LAT, LON, WEEK = 33.69, -78.89, 38      # Myrtle Beach, mid-Sept
MIN_CONF = 0.7

# --- things you own (committed) ---
ASSETS = ROOT / "assets"
ART = ASSETS / "art"                    # Gemini artwork, one PNG per species (was cache/)
FONTS = ASSETS / "fonts"
FONT_REG = str(FONTS / "CormorantGaramond-VariableFont_wght.ttf")
FONT_ITA = str(FONTS / "CormorantGaramond-Italic-VariableFont_wght.ttf")

# --- things the program writes (gitignored) ---
DATA = ROOT / "data"
INBOX = DATA / "inbox"                  # recordings waiting to be analysed
STATE = DATA / "state"                  # heard.json
HISTORY = DATA / "history"              # one snapshot per display update
OUT_DIR = DATA / "out"
OUT = OUT_DIR / "frame.png"             # device image; frame_preview.png and live.html sit beside it
SPECIES_LIST = DATA / "local_species.txt"

# --- dev only ---
CLIPS = ROOT / "dev" / "clips"          # xeno-canto test library (never modified)

ENV_FILE = ROOT / ".env"

for _d in (ART, INBOX, STATE, HISTORY, OUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

W, H = 800, 480                         # Inky Impression 7.3"

GEMINI_MODEL = "gemini-3.1-flash-image"

DEMO_BIRDS = ["Northern Cardinal", "Carolina Chickadee", "Blue Jay",
              "Tufted Titmouse", "Carolina Wren", "Mourning Dove"]
