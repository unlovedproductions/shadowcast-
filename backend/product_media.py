"""Download/cache product stills and composite onto frames/thumbnails."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import numpy as np

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:  # pragma: no cover
    Image = None
    ImageDraw = None
    ImageFilter = None

ASSETS_CACHE = Path(__file__).resolve().parent / "assets" / "product_cache"

_HERO_LAYOUTS = frozenset({"winner_reveal", "price_compare"})
_HERO_TEXT_STYLES = frozenset({"cta_button", "headline_bold", "verdict", "accent_pop"})


def segment_wants_product_hero(seg: dict | None, *, segment_index: int = 0) -> bool:
    """True for hook (first), CTA/verdict styles, and comparison hero layouts."""
    if not seg:
        return segment_index == 0
    layout = str(seg.get("layout") or "")
    if layout in _HERO_LAYOUTS:
        return True
    style = str(seg.get("text_style") or "")
    if style in _HERO_TEXT_STYLES:
        return True
    return segment_index == 0


def _safe_cache_name(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        ext = ".jpg"
    return f"{digest}{ext}"


def resolve_product_image(
    image_url: str | None,
    *,
    cache_dir: Path | None = None,
    timeout: float = 12.0,
) -> Optional[Path]:
    """Download `image_url` into cache (or return existing). Soft-fail → None."""
    url = (image_url or "").strip()
    if not url or not re.match(r"^https?://", url, re.I):
        return None
    if httpx is None or Image is None:
        return None
    dest_dir = cache_dir or ASSETS_CACHE
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _safe_cache_name(url)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            resp = client.get(url, headers={"User-Agent": "ShadowCast/1.0"})
            resp.raise_for_status()
            dest.write_bytes(resp.content)
        # Validate openable image
        with Image.open(dest) as im:
            im.verify()
        return dest
    except Exception:
        try:
            if dest.exists():
                dest.unlink()
        except OSError:
            pass
        return None


def _resample():
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:  # pragma: no cover
        return Image.LANCZOS


def load_rgba(path: Path | str) -> Optional["Image.Image"]:
    if Image is None:
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def fit_contain(img: "Image.Image", max_w: int, max_h: int) -> "Image.Image":
    """Scale image to fit inside max box, preserving aspect."""
    img = img.copy()
    img.thumbnail((max_w, max_h), _resample())
    return img


def paste_product_hero(
    base: "Image.Image",
    product_img: "Image.Image",
    *,
    is_short_form: bool,
    max_frac: float = 0.42,
) -> "Image.Image":
    """Paste product still onto base canvas (upper zone short / left zone long)."""
    if Image is None or ImageDraw is None:
        return base
    canvas = base.convert("RGBA")
    w, h = canvas.size
    if is_short_form:
        box_w, box_h = int(w * 0.72), int(h * max_frac)
        hero = fit_contain(product_img, box_w, box_h)
        x = (w - hero.width) // 2
        y = int(h * 0.12)
    else:
        box_w, box_h = int(w * 0.38), int(h * 0.70)
        hero = fit_contain(product_img, box_w, box_h)
        x = int(w * 0.06)
        y = (h - hero.height) // 2

    # Soft shadow plate
    plate = Image.new("RGBA", (hero.width + 24, hero.height + 24), (0, 0, 0, 0))
    draw = ImageDraw.Draw(plate)
    draw.rounded_rectangle(
        [0, 0, plate.width - 1, plate.height - 1],
        radius=16,
        fill=(0, 0, 0, 120),
    )
    if ImageFilter is not None:
        plate = plate.filter(ImageFilter.GaussianBlur(radius=6))
    canvas.alpha_composite(plate, (x - 12, y - 8))
    canvas.alpha_composite(hero, (x, y))
    return canvas


def frame_with_product_hero(
    frame_arr: np.ndarray,
    product_path: Path | str | None,
    *,
    is_short_form: bool,
) -> np.ndarray:
    """Optionally composite product still onto an RGB/RGBA numpy frame."""
    if not product_path or Image is None:
        return frame_arr
    product = load_rgba(product_path)
    if product is None:
        return frame_arr
    base = Image.fromarray(frame_arr).convert("RGBA")
    out = paste_product_hero(base, product, is_short_form=is_short_form)
    return np.array(out.convert("RGB"))


def thumbnail_with_product_hero(
    base_thumb: "Image.Image",
    product_path: Path | str | None,
) -> "Image.Image":
    """Composite product still onto the right half of a 1280×720 thumbnail."""
    if not product_path or Image is None:
        return base_thumb
    product = load_rgba(product_path)
    if product is None:
        return base_thumb
    canvas = base_thumb.convert("RGBA")
    w, h = canvas.size
    hero = fit_contain(product, int(w * 0.42), int(h * 0.78))
    x = w - hero.width - int(w * 0.05)
    y = (h - hero.height) // 2
    shadow = Image.new("RGBA", (hero.width + 20, hero.height + 20), (0, 0, 0, 0))
    if ImageDraw is not None:
        ImageDraw.Draw(shadow).rounded_rectangle(
            [0, 0, shadow.width - 1, shadow.height - 1],
            radius=12,
            fill=(0, 0, 0, 140),
        )
        if ImageFilter is not None:
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=5))
        canvas.alpha_composite(shadow, (x - 10, y - 6))
    canvas.alpha_composite(hero, (x, y))
    return canvas.convert("RGB")
