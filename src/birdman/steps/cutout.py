"""Step: artwork -> bird with the paper removed."""
import numpy as np
from PIL import Image, ImageFilter


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
