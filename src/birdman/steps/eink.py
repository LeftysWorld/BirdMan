"""Spectra 6 conversion.

The panel is *told* "pure red", but what it physically shows is a dull brick red, and its
"white" is a light grey. So we dither against what the panel really looks like (PANEL),
then hand the device the matching pure colours (INKS). Dithering against pure primaries
instead is what turns a rust-coloured wren into red/green/blue confetti.

render() returns two images built from the same dither:
  device  - pure primaries, this is what you send to the Inky
  preview - the same pixels in PANEL colours, i.e. roughly what the wall will look like
"""
from PIL import Image, ImageEnhance

# Same ink order in both lists: black, white, red, green, blue, yellow.
INKS = [(0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]

# Approximate real-world appearance of Spectra 6 inks. Community measurements vary from
# panel to panel; once yours is on the wall, nudge these until preview.png matches it.
PANEL = [(25, 30, 33), (232, 232, 232), (178, 19, 24), (18, 95, 32), (33, 87, 186), (239, 222, 68)]

SATURATION = 1.15
CONTRAST = 1.10


def _palette_image(colors) -> Image.Image:
    flat = [c for rgb in colors for c in rgb]
    pal = Image.new("P", (1, 1))
    pal.putpalette(flat + flat[:3] * (256 - len(colors)))   # pad with black, never chosen first
    return pal


def prep_for_ink(img: Image.Image) -> Image.Image:
    """Gentle punch, then squeeze the tonal range into what the panel can show."""
    img = ImageEnhance.Color(img.convert("RGB")).enhance(SATURATION)
    img = ImageEnhance.Contrast(img).enhance(CONTRAST)
    lo, hi = PANEL[0], PANEL[1]
    lut = []
    for c in range(3):                                      # paper -> panel white, ink -> panel black
        lut += [round(lo[c] + v * (hi[c] - lo[c]) / 255) for v in range(256)]
    return img.point(lut)


def to_spectra6(img: Image.Image) -> Image.Image:
    """Returns a mode-P image whose indices follow the INKS / PANEL order."""
    return img.quantize(palette=_palette_image(PANEL), dither=Image.FLOYDSTEINBERG)


def _colorize(indexed: Image.Image, colors) -> Image.Image:
    out = indexed.copy()
    flat = [c for rgb in colors for c in rgb]
    out.putpalette(flat + flat[:3] * (256 - len(colors)))
    return out.convert("RGB")


def stamp_text(img: Image.Image, mask: Image.Image, color=(0, 0, 0)) -> Image.Image:
    hard = mask.point(lambda v: 255 if v > 110 else 0)
    img.paste(color, mask=hard)
    return img


def render(artwork: Image.Image, text_mask: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Returns (device image, wall preview)."""
    indexed = to_spectra6(prep_for_ink(artwork))
    device = stamp_text(_colorize(indexed, INKS), text_mask, INKS[0])
    preview = stamp_text(_colorize(indexed, PANEL), text_mask, PANEL[0])
    return device, preview
