"""Turn the chosen hero mouse render into a 2-part cutout rig (HEAD + BODY) for
smooth skeletal animation in Unity.

Steps:
  1. Remove the background (rembg) -> clean RGBA mouse, trimmed to content.
  2. Find the NECK = narrowest silhouette row between head and body.
  3. Split into two full-canvas layers that overlap around the neck so the head
     can bob/tilt without opening a transparent gap:
        head_layer = pixels above (neck + overlap)
        body_layer = pixels below (neck - overlap)
  4. Save head/body PNGs (same canvas size, so they align when stacked), a
     rig.json with the neck pivot, plus seam-check previews.

Run with the imgenv venv (rembg installed there).
"""
import json
import os

import numpy as np
from PIL import Image
from rembg import remove

SRC = r"C:\Users\Sergi-Teknik\GestureExhibit\art_in\hero_2.png"
OUT = r"C:\Users\Sergi-Teknik\GestureExhibit\unity\Assets\Art\mouse"
os.makedirs(OUT, exist_ok=True)

ALPHA_THR = 24          # alpha above this counts as "mouse"
NECK_BAND = (0.30, 0.62)  # search the neck in this vertical fraction band
OVERLAP_FRAC = 0.09      # head/body overlap (fraction of height) around the neck


def _trim(img: Image.Image) -> Image.Image:
    bbox = img.split()[-1].getbbox()
    return img.crop(bbox) if bbox else img


def main():
    print("removing background...")
    src = Image.open(SRC).convert("RGBA")
    mouse = remove(src)            # RGBA, background cleared
    mouse = _trim(mouse)
    W, H = mouse.size
    print(f"clean mouse: {W}x{H}")
    mouse.save(os.path.join(OUT, "mouse_full.png"))

    alpha = np.array(mouse.split()[-1])
    rows = (alpha > ALPHA_THR).sum(axis=1).astype(np.float32)
    # smooth the row-width profile a little
    k = max(3, int(H * 0.02))
    ker = np.ones(k) / k
    smooth = np.convolve(rows, ker, mode="same")

    y0, y1 = int(NECK_BAND[0] * H), int(NECK_BAND[1] * H)
    neck_y = y0 + int(np.argmin(smooth[y0:y1]))
    print(f"neck row: {neck_y} ({neck_y / H:.2f} of height), "
          f"width there: {int(rows[neck_y])}px vs head-max {int(rows[:y0].max())}")

    overlap = int(OVERLAP_FRAC * H)
    arr = np.array(mouse)

    # HEAD: keep rows [0, neck_y + overlap)
    head = arr.copy()
    head[neck_y + overlap:, :, 3] = 0
    # BODY: keep rows [neck_y - overlap, H)
    body = arr.copy()
    body[:max(0, neck_y - overlap), :, 3] = 0

    Image.fromarray(head, "RGBA").save(os.path.join(OUT, "mouse_head.png"))
    Image.fromarray(body, "RGBA").save(os.path.join(OUT, "mouse_body.png"))

    # Head pivot = neck joint. x = centroid of head pixels, y = neck row.
    head_alpha = alpha[:neck_y]
    if head_alpha.sum() > 0:
        xs = np.arange(W)[None, :].repeat(neck_y, axis=0)
        cx = float((xs * (head_alpha > ALPHA_THR)).sum() / max(1, (head_alpha > ALPHA_THR).sum()))
    else:
        cx = W / 2.0
    pivot = [cx / W, 1.0 - neck_y / H]   # Unity pivot: (x from left, y from BOTTOM)
    with open(os.path.join(OUT, "rig.json"), "w") as f:
        json.dump({"canvas": [W, H], "neck_pivot": pivot, "neck_y": neck_y}, f, indent=2)
    print("head pivot (unity):", pivot)

    # --- seam-check previews ------------------------------------------------
    rest = Image.alpha_composite(Image.fromarray(body, "RGBA"),
                                 Image.fromarray(head, "RGBA"))
    rest.save(os.path.join(OUT, "_preview_rest.png"))

    # head lifted + tilted (panic-ish) to check for gaps at the neck
    head_img = Image.fromarray(head, "RGBA")
    dy = int(0.06 * H)
    moved = head_img.rotate(8, resample=Image.BICUBIC, center=(cx, neck_y))
    canvas = Image.fromarray(body, "RGBA").copy()
    canvas.alpha_composite(moved, (0, -dy))
    canvas.save(os.path.join(OUT, "_preview_headup.png"))

    print("wrote head/body/full + rig.json + previews to", OUT)


if __name__ == "__main__":
    main()
