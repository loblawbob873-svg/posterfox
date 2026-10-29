#!/usr/bin/env python3
"""Draw PosterFox's branding images from the PosterChan icon (branding/src/icon-512.png).

    tools/make-branding.py OUT_DIR

Writes every image Mozilla's browser/branding/unofficial ships, at the sizes it ships them, so the branding dir is
complete and no Firefox/Nightly artwork shows through: the default*.png app icons, the About dialog logos (normal
and private, 1x and 2x), about.png, the Windows tile images, and the two wordmarks (SVG, "PosterFox" in the neon
accent, `context-fill` so the about dialog can recolour it). Deterministic: same source, same bytes.
"""
import base64
import io
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = pathlib.Path(__file__).resolve().parent.parent
SRC = HERE / "branding" / "src" / "icon-512.png"
NEON, NEON2, BG = (60, 232, 255), (255, 92, 240), (10, 10, 15)


def _png(img: Image.Image) -> bytes:
    b = io.BytesIO()
    img.save(b, "PNG", optimize=True)
    return b.getvalue()


def icon(size: int) -> Image.Image:
    return Image.open(SRC).convert("RGBA").resize((size, size), Image.LANCZOS)


def private_icon(size: int) -> Image.Image:
    """The private-browsing logo: the same icon in a magenta ring, so it is never mistaken for a normal window."""
    base = icon(size)
    ring = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(ring)
    w = max(2, size // 24)
    d.ellipse([w, w, size - w - 1, size - w - 1], outline=NEON2 + (255,), width=w)
    glow = ring.filter(ImageFilter.GaussianBlur(w))
    out = Image.alpha_composite(base, glow)
    return Image.alpha_composite(out, ring)


def about_png() -> Image.Image:
    """300x236 About image: the icon centred on the PosterChan night background with a neon underline."""
    im = Image.new("RGBA", (300, 236), BG + (255,))
    ic = icon(168)
    im.alpha_composite(ic, ((300 - 168) // 2, 18))
    d = ImageDraw.Draw(im)
    d.rectangle([60, 206, 240, 209], fill=NEON + (255,))
    return im


WORDMARK = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 372 99">
  <text x="0" y="74" font-family="Orbitron, Inter, sans-serif" font-size="74" font-weight="700" letter-spacing="1"
        fill="context-fill">PosterFox</text>
</svg>
"""


def write(out: pathlib.Path):
    out.mkdir(parents=True, exist_ok=True)
    (out / "content").mkdir(exist_ok=True)
    files = {}
    for s in (16, 22, 24, 32, 48, 64, 128, 256):
        files[f"default{s}.png"] = _png(icon(s))
    for name, s in (("VisualElements_70.png", 142), ("VisualElements_150.png", 300)):
        files[name] = _png(icon(s))
    for name, s in (("PrivateBrowsing_70.png", 142), ("PrivateBrowsing_150.png", 300)):
        files[name] = _png(private_icon(s))
    files["content/about-logo.png"] = _png(icon(192))
    files["content/about-logo@2x.png"] = _png(icon(384))
    files["content/about-logo-private.png"] = _png(private_icon(192))
    files["content/about-logo-private@2x.png"] = _png(private_icon(384))
    files["content/about.png"] = _png(about_png())
    b64 = base64.b64encode(_png(icon(512))).decode()
    files["content/about-logo.svg"] = (f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512">'
                                       f'<image width="512" height="512" href="data:image/png;base64,{b64}"/></svg>\n').encode()
    files["content/about-wordmark.svg"] = WORDMARK.encode()
    files["content/firefox-wordmark.svg"] = WORDMARK.encode()
    for rel, data in files.items():
        (out / rel).write_bytes(data)
    return sorted(files)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print("\n".join(write(pathlib.Path(sys.argv[1]))))
