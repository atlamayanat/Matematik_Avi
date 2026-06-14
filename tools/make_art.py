"""Generate placeholder art for the Cheese-Hunt gesture game.

- mouse + cheese  : downloaded from OpenMoji (CC BY-SA 4.0) and composited into
                    one "mouse eating cheese" sprite. Falls back to drawn shapes
                    if the download fails (offline).
- spotlight circle: soft white radial alpha disc (used by the Unity SpriteMask).
- spotlight ring  : glowing ring drawn on top so the player sees the magnifier edge.
- net             : translucent mesh hoop that drops on a catch.

Run with the project venv python (Pillow is already installed):
    .venv\\Scripts\\python.exe tools\\make_art.py
Outputs PNGs into unity/Assets/Art/.
"""
from __future__ import annotations

import os
import urllib.request

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.normpath(os.path.join(HERE, "..", "unity", "Assets", "Art"))
os.makedirs(ART, exist_ok=True)


def _download(codepoint: str) -> Image.Image | None:
    """Fetch one OpenMoji 618px color PNG by codepoint, or None on failure."""
    urls = [
        f"https://cdn.jsdelivr.net/gh/hfg-gmuend/openmoji@master/color/618x618/{codepoint}.png",
        f"https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/618x618/{codepoint}.png",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            from io import BytesIO
            img = Image.open(BytesIO(data)).convert("RGBA")
            print(f"  downloaded {codepoint} from {url} ({len(data)} bytes)")
            return img
        except Exception as e:  # noqa: BLE001
            print(f"  failed {url}: {e}")
    return None


def _trim(img: Image.Image) -> Image.Image:
    """Crop to the non-transparent bounding box."""
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def make_mouse_cheese(size: int = 512) -> None:
    mouse = _download("1F401")   # mouse (full body)
    cheese = _download("1F9C0")  # cheese wedge
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    if mouse is not None and cheese is not None:
        mouse = _trim(mouse)
        cheese = _trim(cheese)
        # Cheese sits lower-left, mouse leans in from the right (eating it).
        ch = int(size * 0.55)
        cheese = cheese.resize((ch, ch), Image.LANCZOS)
        mo = int(size * 0.62)
        mouse = mouse.resize((mo, mo), Image.LANCZOS)
        canvas.alpha_composite(cheese, (int(size * 0.05), int(size * 0.40)))
        canvas.alpha_composite(mouse, (int(size * 0.38), int(size * 0.30)))
    else:
        # Offline fallback: a grey mouse blob + yellow cheese triangle.
        d = ImageDraw.Draw(canvas)
        d.polygon([(40, 460), (300, 460), (300, 250)], fill=(255, 205, 60, 255))
        for hx, hy in [(120, 430), (190, 400), (250, 360), (160, 350)]:
            d.ellipse([hx, hy, hx + 26, hy + 26], fill=(235, 175, 40, 255))
        d.ellipse([300, 250, 470, 420], fill=(150, 150, 158, 255))   # body
        d.ellipse([430, 230, 500, 300], fill=(150, 150, 158, 255))   # head
        d.ellipse([452, 215, 480, 243], fill=(190, 150, 160, 255))   # ear
        d.ellipse([470, 262, 482, 274], fill=(20, 20, 20, 255))      # eye

    out = os.path.join(ART, "mouse_cheese.png")
    canvas.save(out)
    print("wrote", out)


def make_circle(size: int = 512) -> None:
    """Soft white radial disc for the SpriteMask (alpha falls off near the edge)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    c = size / 2.0
    r = c - 2
    for y in range(size):
        for x in range(size):
            d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5
            if d <= r:
                # full alpha inside, soft 12% feather at the rim
                edge = max(0.0, (d - r * 0.88) / (r * 0.12))
                a = int(255 * (1.0 - min(1.0, edge)))
                px[x, y] = (255, 255, 255, a)
    out = os.path.join(ART, "spotlight_circle.png")
    img.save(out)
    print("wrote", out)


def make_ring(size: int = 512) -> None:
    """Glowing visible ring (the magnifier edge), soft premium light-beam look.
    Widths scale with size so a 1024px ring is crisp but not hair-thin."""
    s = size / 512.0
    c = size / 2.0
    r = c - 30 * s
    box = [c - r, c - r, c + r, c + r]
    # wide soft outer glow
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(box, outline=(120, 195, 255, 255), width=int(34 * s))
    glow = glow.filter(ImageFilter.GaussianBlur(18 * s))
    # crisp bright rim on top
    rim = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(rim).ellipse(box, outline=(245, 251, 255, 255), width=int(9 * s))
    rim = rim.filter(ImageFilter.GaussianBlur(1.2 * s))
    img = Image.alpha_composite(glow, rim)
    out = os.path.join(ART, "spotlight_ring.png")
    img.save(out)
    print("wrote", out)


def make_bg(size: int = 512) -> None:
    """Pale-blue 'revealed world' disc shown INSIDE the spotlight, matching the
    reference look (soft blue circle under the magnifier)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    c = size / 2.0
    r = c - 2
    inner = (226, 243, 255)   # near-white blue at the centre
    outer = (150, 200, 240)   # deeper blue near the rim
    for y in range(size):
        for x in range(size):
            d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5
            if d <= r:
                t = d / r
                col = tuple(int(inner[i] + (outer[i] - inner[i]) * t) for i in range(3))
                edge = max(0.0, (d - r * 0.92) / (r * 0.08))
                a = int(255 * (1.0 - min(1.0, edge)))
                px[x, y] = (col[0], col[1], col[2], a)
    out = os.path.join(ART, "bg_reveal.png")
    img.save(out)
    print("wrote", out)


def make_net(size: int = 512) -> None:
    """Translucent mesh hoop that drops on a catch."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = size / 2.0
    r = c - 24
    # mesh crosshatch clipped to the disc
    step = 34
    mesh = (255, 255, 255, 90)
    for off in range(-size, size, step):
        d.line([(0, off), (size, off + size)], fill=mesh, width=3)
        d.line([(0, off + size), (size, off)], fill=mesh, width=3)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([c - r, c - r, c + r, c + r], fill=255)
    img.putalpha(Image.composite(img.getchannel("A"), Image.new("L", (size, size), 0), mask))
    d = ImageDraw.Draw(img)
    d.ellipse([c - r, c - r, c + r, c + r], outline=(90, 60, 40, 255), width=12)  # hoop
    out = os.path.join(ART, "net.png")
    img.save(out)
    print("wrote", out)


def write_credits() -> None:
    out = os.path.join(ART, "CREDITS.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(
            "mouse_cheese.png is composited from OpenMoji emoji (mouse 1F401, "
            "cheese 1F9C0).\n"
            "OpenMoji - the open-source emoji and icon project. "
            "License: CC BY-SA 4.0.\n"
            "https://openmoji.org/  https://creativecommons.org/licenses/by-sa/4.0/\n\n"
            "spotlight_circle.png, spotlight_ring.png, net.png are generated "
            "procedurally for this project (no third-party rights).\n"
        )
    print("wrote", out)


if __name__ == "__main__":
    print("Generating art into", ART)
    make_mouse_cheese()
    make_circle(1024)
    make_ring(1024)
    make_bg(1024)
    make_net(1024)
    write_credits()
    print("done.")
