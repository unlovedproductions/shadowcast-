"""Lightweight visual quality checks for thumbnails and frames."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover
    np = None
    Image = None

MIN_WCAG_CONTRAST = 4.5


def _relative_luminance(channel: float) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def contrast_ratio(l1: float, l2: float) -> float:
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def measure_image_contrast(path: Path) -> Optional[dict]:
    if Image is None or np is None or not path.exists():
        return None
    img = Image.open(path).convert("RGB")
    arr = np.asarray(img, dtype=np.float32)
    flat = arr.reshape(-1, 3)
    sample = flat[:: max(1, len(flat) // 5000)]
    luminance = 0.2126 * sample[:, 0] + 0.7152 * sample[:, 1] + 0.0722 * sample[:, 2]
    dark = float(np.percentile(luminance, 10))
    bright = float(np.percentile(luminance, 90))
    l_dark = _relative_luminance(dark)
    l_bright = _relative_luminance(bright)
    ratio = contrast_ratio(l_dark, l_bright)
    return {
        "contrast_ratio": round(ratio, 2),
        "passes_wcag_aa": ratio >= MIN_WCAG_CONTRAST,
        "dark_luma": round(dark, 1),
        "bright_luma": round(bright, 1),
    }


def audit_thumbnail_contrast(path: Path) -> tuple[str, str, str, str]:
    metrics = measure_image_contrast(path)
    if metrics is None:
        return "WARN", f">={MIN_WCAG_CONTRAST}:1", "unavailable", "Could not measure thumbnail contrast."
    ratio = metrics["contrast_ratio"]
    if metrics["passes_wcag_aa"]:
        return "PASS", f">={MIN_WCAG_CONTRAST}:1", f"{ratio}:1", "Thumbnail luminance contrast is acceptable."
    return (
        "WARN",
        f">={MIN_WCAG_CONTRAST}:1",
        f"{ratio}:1",
        "Thumbnail may have low text/background separation.",
    )
