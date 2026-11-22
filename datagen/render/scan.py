"""Turn a rendered PDF page into a degraded, scan-like image."""

from __future__ import annotations

import io
import random

import pypdfium2 as pdfium
from PIL import Image, ImageFilter


def pdf_to_scan(pdf: bytes, rng: random.Random, dpi: int = 150) -> bytes:
    """Rasterise page 1, convert to grey, rotate slightly, add blur and noise, save as PNG.

    PNG keeps the output deterministic across platforms (JPEG encoders differ)."""
    doc = pdfium.PdfDocument(pdf)
    try:
        page = doc[0]
        img = page.render(scale=dpi / 72).to_pil().convert("L")
    finally:
        doc.close()
    angle = rng.uniform(-1.8, 1.8)
    img = img.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=255)
    img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.3, 0.9)))
    noise_rng = random.Random(rng.random())
    px = img.load()
    assert px is not None  # noqa: S101
    w, h = img.size
    for _ in range(w * h // 180):  # salt-and-pepper speckles
        x, y = noise_rng.randrange(w), noise_rng.randrange(h)
        px[x, y] = 0 if noise_rng.random() < 0.5 else 255
    # slightly uneven exposure
    img = img.point(lambda value: min(255, int(value * 0.93 + 18)))
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()
