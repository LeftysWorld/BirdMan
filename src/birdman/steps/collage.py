"""Honeycomb collage: one hero bird in the middle, everyone else packed tight around it.

Layout is a silhouette packer, not a fixed grid:
  1. every bird gets a pixel mask, plus a "halo" (the mask grown by GAP px)
  2. the hero goes dead centre
  3. each following bird takes the free spot closest to the centre, measured on an
     ellipse shaped like the field, with a gentle pull toward its own compass bearing
     so the ring fills evenly instead of piling up on one side
  4. if anything fails to fit, the whole flock shrinks a little and we try again
  5. the finished cluster is re-centred in the field

Works for 1 bird or 15. "Free spot" is computed for every position at once with an FFT
cross-correlation, so a full pack is a handful of FFTs rather than thousands of probes.
"""
import math
import random
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageFilter

from birdman.config import W, H, FONT_REG, FONT_ITA
from birdman.steps.illustrate import bird_image
from birdman.steps.cutout import cutout
from birdman.clock import now, today

# ---- layout knobs -----------------------------------------------------------------
MAX_BIRDS = 15
MARGIN = 28                 # paper left/right of the cluster
HEADER_H = 94               # date + title live above this line
CAPTION_LINE_H = 19
CAPTION_MAX_LINES = 3
CAPTION_PAD = 20            # paper below the caption

GAP = 6                     # px of paper between neighbouring birds
SMALL = (0.50, 0.64)        # supporting birds, relative to the hero
HERO_MAX = 0.80             # hero never taller/wider than this share of field height
FILL = 0.80                 # optimistic first guess at how much field the flock can cover
SHRINK = 0.93               # scale step when a pack attempt fails
REACH = 0.92                # how far (0..1 of the field ellipse) a bird's centre may sit
ANGLE_PULL = 0.30           # 0 = pure closest-to-centre, higher = more even ring
GOLDEN = math.pi * (3 - math.sqrt(5))

# Small text is hard-thresholded to 1-bit ink in eink.stamp_text (cut-off 110/255).
# Cormorant's hairlines never reach that at 16-18px, so they vanish. Small text is drawn
# on its own layer at full weight and its coverage multiplied by FINE_BOOST before the
# threshold, which keeps the hairlines. Too thin still -> raise it. Counters of a/e
# filling in -> lower it. The title is untouched.
FINE_WEIGHT = 700
FINE_BOOST = 2.0
DATE_PX = 18
CAPTION_PX = 17

MASTER = 400                # working resolution for cleaned sprites
ALPHA_T = 40                # alpha above this counts as "bird"


# ---- fonts ------------------------------------------------------------------------
def font(path: str, size: int, weight: int = 600):
    try:
        f = ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()
    try:
        f.set_variation_by_axes([weight])
    except OSError:
        pass                                    # static font: use as-is
    return f


# ---- sprites ----------------------------------------------------------------------
def _grow(m: np.ndarray) -> np.ndarray:
    """3x3 binary dilation."""
    v = m.copy()
    v[1:] |= m[:-1]
    v[:-1] |= m[1:]
    o = v.copy()
    o[:, 1:] |= v[:, :-1]
    o[:, :-1] |= v[:, 1:]
    return o


def _body_only(solid: np.ndarray) -> np.ndarray:
    """Keep only pixels connected to the bird's body; stray specks are dropped.

    Opening-by-reconstruction at half resolution: erode until only the thick body
    survives, then grow that seed back *inside* the silhouette. Legs, beak and tail
    come back because they are attached; floating specks never get reached.
    """
    h, w = solid.shape
    ph, pw = (-h) % 2, (-w) % 2
    pooled = np.pad(solid, ((0, ph), (0, pw)))
    pooled = pooled.reshape(pooled.shape[0] // 2, 2, pooled.shape[1] // 2, 2).any(axis=(1, 3))
    pooled = _grow(pooled)                      # bridge hairline breaks in the keyline

    hole = ~pooled
    for _ in range(6):
        hole = _grow(hole)
    seed = ~hole
    if not seed.any():
        return solid

    while True:
        nxt = _grow(seed) & pooled
        if np.array_equal(nxt, seed):
            break
        seed = nxt

    keep = np.repeat(np.repeat(seed, 2, axis=0), 2, axis=1)[:h, :w]
    return solid & keep


@lru_cache(maxsize=64)
def _master(name: str) -> Image.Image:
    """Cleaned, tightly cropped RGBA sprite at working resolution. Treat as read-only."""
    img = cutout(bird_image(name)).convert("RGBA")
    img.thumbnail((MASTER, MASTER), Image.LANCZOS)
    alpha = np.array(img.getchannel("A"))
    keep = _body_only(alpha > ALPHA_T)
    img.putalpha(Image.fromarray(np.where(keep, alpha, 0).astype(np.uint8)))
    box = img.getchannel("A").point(lambda v: 255 if v > ALPHA_T else 0).getbbox()
    return img.crop(box) if box else img


def _sprite(name: str, size: int, flip: bool) -> Image.Image:
    """The bird scaled so its longest side is `size` px."""
    m = _master(name)
    s = size / max(m.size)
    img = m.resize((max(1, round(m.width * s)), max(1, round(m.height * s))), Image.LANCZOS)
    return img.transpose(Image.FLIP_LEFT_RIGHT) if flip else img


def _masks(img: Image.Image) -> tuple[np.ndarray, np.ndarray]:
    """(body, halo). halo is body grown by GAP on a canvas padded by GAP each side."""
    a = img.getchannel("A").point(lambda v: 255 if v > ALPHA_T else 0)
    padded = Image.new("L", (img.width + 2 * GAP, img.height + 2 * GAP), 0)
    padded.paste(a, (GAP, GAP))
    halo = np.array(padded.filter(ImageFilter.MaxFilter(2 * GAP + 1))) > 0
    return np.array(a) > 0, halo


# ---- layout records (private to this step) ----------------------------------------
@dataclass(frozen=True)
class BirdPlan:
    """How one bird should appear today, decided before any packing is attempted."""
    name: str
    scale: float            # size relative to the hero (the hero is 1.0)
    flip: bool              # face right instead of left
    bearing: float          # preferred compass direction from the hero, in radians


@dataclass(frozen=True)
class Placement:
    """A finished sprite and where its top-left corner goes."""
    sprite: Image.Image
    x: int
    y: int

    @property
    def right(self) -> int:
        return self.x + self.sprite.width

    @property
    def bottom(self) -> int:
        return self.y + self.sprite.height

    def moved(self, dx: int, dy: int) -> "Placement":
        return Placement(self.sprite, self.x + dx, self.y + dy)


# ---- packing ----------------------------------------------------------------------
def _fast_len(n: int) -> int:
    """Next size whose only prime factors are 2, 3, 5 (keeps the FFT quick)."""
    while True:
        m = n
        for p in (2, 3, 5):
            while m % p == 0:
                m //= p
        if m == 1:
            return n
        n += 1


def _try_pack(plan: list[BirdPlan], hero_px: float, fw: int, fh: int) -> list[Placement] | None:
    """Place every bird in `plan` inside an fw x fh field. None if something won't fit."""
    shape = (_fast_len(fh), _fast_len(fw))
    occ = np.zeros((fh, fw), dtype=bool)
    placed = []
    for i, bird in enumerate(plan):
        img = _sprite(bird.name, max(8, int(hero_px * bird.scale)), bird.flip)
        body, halo = _masks(img)
        if not body.any():
            continue
        hh, hw = halo.shape
        if hh > fh or hw > fw:
            return None

        # where would this bird's centre of mass land, for every possible top-left?
        ys, xs = np.nonzero(body)
        gx = (np.arange(fw - hw + 1) + xs.mean() + GAP - fw / 2) / (fw / 2)
        gy = (np.arange(fh - hh + 1) + ys.mean() + GAP - fh / 2) / (fh / 2)
        r = np.hypot(gx[None, :], gy[:, None])

        if i == 0:
            cost = r
        else:
            bearing = np.arctan2(gy[:, None], gx[None, :])
            cost = r * (1 + ANGLE_PULL * (1 - np.cos(bearing - bird.bearing)))
            # overlap[y, x] = how many occupied pixels the halo would cover at (x, y)
            overlap = np.fft.irfft2(
                np.fft.rfft2(occ.astype(np.float64), shape)
                * np.conj(np.fft.rfft2(halo.astype(np.float64), shape)),
                shape,
            )[: fh - hh + 1, : fw - hw + 1]
            cost = np.where(overlap < 0.5, cost, np.inf)

        j = int(np.argmin(cost))
        y, x = divmod(j, cost.shape[1])
        if not np.isfinite(cost[y, x]) or r[y, x] > REACH:
            return None
        x, y = x + GAP, y + GAP                 # halo offset -> sprite offset
        occ[y:y + body.shape[0], x:x + body.shape[1]] |= body
        placed.append(Placement(img, x, y))
    return placed


def _traits(name: str, day: str) -> tuple[float, bool]:
    """A bird's relative size and facing, fixed for the day no matter who else shows up."""
    r = random.Random(f"{day}|{name}")
    return r.uniform(*SMALL), r.random() < 0.5


def _compose(names: list[str], day: str, field) -> list[Placement]:
    """Returns the placed birds in canvas coordinates.

    `names` is in arrival order: names[0] is the hero, later birds are placed in the order
    they were first heard. Every random choice is keyed to (day, name) or to arrival
    position, so when a new species turns up the flock *grows* - existing birds keep their
    size, facing and side of the hero - instead of being reshuffled from scratch.
    """
    fx0, fy0, fx1, fy1 = field
    fw, fh = fx1 - fx0, fy1 - fy0
    n = len(names)

    theta0 = random.Random(day).uniform(0, 2 * math.pi)
    plan = [BirdPlan(names[0], 1.0, _traits(names[0], day)[1], 0.0)]
    for k, nm in enumerate(names[1:]):
        scale, flip = _traits(nm, day)
        plan.append(BirdPlan(nm, scale, flip, theta0 + k * GOLDEN))

    mean_small_area = ((SMALL[0] + SMALL[1]) / 2) ** 2
    hero = min(HERO_MAX * fh, math.sqrt(FILL * fw * fh / (1 + (n - 1) * mean_small_area)))

    placed = None
    for _ in range(40):
        placed = _try_pack(plan, hero, fw, fh)
        if placed is not None:
            break
        hero *= SHRINK
    if not placed:
        return []

    # centre the finished cluster in the field
    bx0 = min(p.x for p in placed)
    by0 = min(p.y for p in placed)
    bx1 = max(p.right for p in placed)
    by1 = max(p.bottom for p in placed)
    ox = fx0 + (fw - (bx1 - bx0)) // 2 - bx0
    oy = fy0 + (fh - (by1 - by0)) // 2 - by0
    return [p.moved(ox, oy) for p in placed]


# ---- text -------------------------------------------------------------------------
def _tracked(td, text: str, f, y: int, tracking: int):
    widths = [td.textlength(ch, font=f) for ch in text]
    x = (W - (sum(widths) + tracking * (len(text) - 1))) / 2
    for ch, w in zip(text, widths):
        td.text((x, y), ch, fill=255, font=f)
        x += w + tracking


def _draw_label(td, fd, count: int):
    """Title goes on the normal text layer (td), the date on the fine-text layer (fd)."""
    date_f = font(FONT_ITA, DATE_PX, FINE_WEIGHT)
    date = f"{now():%A, %B %-d}  ·  {count} species"
    fd.text(((W - fd.textlength(date, font=date_f)) / 2, 15), date, fill=255, font=date_f)
    _tracked(td, "HEARD TODAY", font(FONT_REG, 44, 700), 36, tracking=4)


def _caption_lines(td, names: list[str], hidden: int, f) -> list[str]:
    """Names joined with dots, wrapped to CAPTION_MAX_LINES; overflow becomes '+ N more'."""
    sep = "  ·  "
    max_w = W - 2 * (MARGIN + 12)

    def wrap(items):
        lines, cur = [], []
        for it in items:
            if cur and td.textlength(sep.join(cur + [it]), font=f) > max_w:
                lines.append(sep.join(cur))
                cur = [it]
            else:
                cur.append(it)
        return lines + [sep.join(cur)]

    keep = len(names)
    while True:
        more = hidden + len(names) - keep
        items = names[:keep] + ([f"+ {more} more"] if more else [])
        lines = wrap(items)
        if len(lines) <= CAPTION_MAX_LINES or keep <= 1:
            return lines[:CAPTION_MAX_LINES]
        keep -= 1


def _draw_caption(td, lines: list[str], f):
    y = H - CAPTION_PAD - CAPTION_LINE_H * len(lines)
    for ln in lines:
        td.text(((W - td.textlength(ln, font=f)) / 2, y), ln, fill=255, font=f)
        y += CAPTION_LINE_H


# ---- entry point ------------------------------------------------------------------
def _draw_quiet_day(fd):
    """Nothing heard yet: a calm plate instead of an empty one."""
    f = font(FONT_ITA, 22, FINE_WEIGHT)
    msg = "listening\u2026"
    fd.text(((W - fd.textlength(msg, font=f)) / 2, (HEADER_H + H) // 2 - 22), msg, fill=255, font=f)


def build_collage(names: list[str]) -> tuple[Image.Image, Image.Image]:
    """Returns (artwork RGB, text mask L). Text is stamped after quantizing.

    `names` may be empty (start of the day). A species whose artwork isn't available yet
    (Gemini unreachable) is still named in the caption - it *was* heard - and its bird
    joins the flock on a later redraw once the art exists.
    """
    canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    text = Image.new("L", (W, H), 0)
    fine = Image.new("L", (W, H), 0)            # small text, boosted before thresholding
    td, fd = ImageDraw.Draw(text), ImageDraw.Draw(fine)

    _draw_label(td, fd, len(names))
    if names:
        shown = names[:MAX_BIRDS]
        cap_f = font(FONT_ITA, CAPTION_PX, FINE_WEIGHT)
        lines = _caption_lines(fd, shown, len(names) - len(shown), cap_f)
        caption_top = H - CAPTION_PAD - CAPTION_LINE_H * len(lines)
        field = (MARGIN, HEADER_H, W - MARGIN, caption_top - 10)

        drawable = [n for n in shown if bird_image(n) is not None]
        if drawable:
            for p in _compose(drawable, today(), field):
                canvas.alpha_composite(p.sprite, (p.x, p.y))
        _draw_caption(fd, lines, cap_f)
    else:
        _draw_quiet_day(fd)

    fine = fine.point(lambda v: min(255, int(v * FINE_BOOST)))
    text = ImageChops.lighter(text, fine)
    return canvas.convert("RGB"), text
