"""Lightweight visual quality checks for thumbnails and frames."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

MIN_WCAG_CONTRAST = 4.5
# Conservative Laplacian variance floor for muddy marketplace thumbs (~160px).
MIN_PRODUCT_SHARPNESS = 40.0
CAPTION_SCRIM_MIN_CONTRAST = 3.0


def _relative_luminance(channel: float) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def contrast_ratio(l1: float, l2: float) -> float:
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _as_rgb_float(arr) -> Optional["np.ndarray"]:
    if np is None or arr is None:
        return None
    a = np.asarray(arr)
    if a.ndim == 2:
        a = np.stack([a, a, a], axis=-1)
    if a.ndim != 3 or a.shape[2] < 3:
        return None
    return a[..., :3].astype(np.float32)


def _to_gray(rgb: "np.ndarray") -> "np.ndarray":
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def laplacian_variance(arr) -> Optional[float]:
    """3x3 Laplacian variance — blur proxy without OpenCV."""
    rgb = _as_rgb_float(arr)
    if rgb is None or np is None:
        return None
    gray = _to_gray(rgb)
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    # Discrete Laplacian kernel
    kernel = np.array([[0.0, 1.0, 0.0], [1.0, -4.0, 1.0], [0.0, 1.0, 0.0]], dtype=np.float32)
    # Valid convolution via scipy-free sliding windows
    g = gray
    lap = (
        kernel[0, 1] * g[:-2, 1:-1]
        + kernel[1, 0] * g[1:-1, :-2]
        + kernel[1, 1] * g[1:-1, 1:-1]
        + kernel[1, 2] * g[1:-1, 2:]
        + kernel[2, 1] * g[2:, 1:-1]
    )
    return float(np.var(lap))


def energy_bbox(
    arr,
    *,
    percentile: float = 90.0,
    pad: float = 0.06,
) -> Optional[tuple[int, int, int, int]]:
    """
    Bounding box of high-frequency pixels (gradient magnitude).

    Returns (left, top, right, bottom) inclusive-exclusive crop box, or None.
    """
    rgb = _as_rgb_float(arr)
    if rgb is None or np is None:
        return None
    gray = _to_gray(rgb)
    h, w = gray.shape
    if h < 4 or w < 4:
        return (0, 0, w, h)
    gx = np.abs(gray[:, 1:] - gray[:, :-1])
    gy = np.abs(gray[1:, :] - gray[:-1, :])
    # Align to (h-1, w-1)
    energy = gx[:-1, :] + gy[:, :-1]
    thr = float(np.percentile(energy, percentile))
    mx = float(np.max(energy))
    if mx <= 1e-6:
        return (0, 0, w, h)
    # Sparse edges (solid subject on flat pad): percentile of mostly-zeros is ~0.
    if thr <= 1e-6:
        thr = mx * 0.25
    ys, xs = np.where(energy >= thr)
    if len(xs) == 0:
        return (0, 0, w, h)
    left, right = int(xs.min()), int(xs.max()) + 1
    top, bottom = int(ys.min()), int(ys.max()) + 1
    # Map from (h-1,w-1) energy grid back toward full image; pad fractionally.
    pad_x = max(1, int(w * pad))
    pad_y = max(1, int(h * pad))
    left = max(0, left - pad_x)
    top = max(0, top - pad_y)
    right = min(w, right + pad_x + 1)
    bottom = min(h, bottom + pad_y + 1)
    if right - left < max(8, w // 10) or bottom - top < max(8, h // 10):
        return (0, 0, w, h)
    return (left, top, right, bottom)


def studio_bg_mask(arr) -> Optional["np.ndarray"]:
    """
    Soft alpha matte for near-white studio backgrounds.

    Returns HxW float alpha in [0,1], or None when heuristic should not fire
    (protects white products / non-studio shots).
    """
    rgb = _as_rgb_float(arr)
    if rgb is None or np is None:
        return None
    h, w = rgb.shape[:2]
    if h < 16 or w < 16:
        return None
    gray = _to_gray(rgb)
    corner = max(4, min(h, w) // 10)

    def _patch_stats(y0, y1, x0, x1):
        patch = gray[y0:y1, x0:x1]
        return float(np.mean(patch)), float(np.var(patch))

    corners = [
        _patch_stats(0, corner, 0, corner),
        _patch_stats(0, corner, w - corner, w),
        _patch_stats(h - corner, h, 0, corner),
        _patch_stats(h - corner, h, w - corner, w),
    ]
    corner_means = [m for m, _ in corners]
    corner_vars = [v for _, v in corners]
    if min(corner_means) < 220.0 or max(corner_vars) > 400.0:
        return None

    cy0, cy1 = h // 3, (2 * h) // 3
    cx0, cx1 = w // 3, (2 * w) // 3
    center_mean = float(np.mean(gray[cy0:cy1, cx0:cx1]))
    # Center must be meaningfully darker than white studio corners.
    if center_mean > 200.0:
        return None  # white-on-white — skip
    if center_mean > float(np.mean(corner_means)) - 25.0:
        return None

    # Soft matte: white → transparent, darker → opaque.
    alpha = np.clip((240.0 - gray) / 80.0, 0.0, 1.0)
    # Slight edge soften via box blur (3x3 mean)
    padded = np.pad(alpha, 1, mode="edge")
    alpha = (
        padded[:-2, :-2]
        + padded[:-2, 1:-1]
        + padded[:-2, 2:]
        + padded[1:-1, :-2]
        + padded[1:-1, 1:-1]
        + padded[1:-1, 2:]
        + padded[2:, :-2]
        + padded[2:, 1:-1]
        + padded[2:, 2:]
    ) / 9.0
    return alpha.astype(np.float32)


def region_mean_luma(arr, box: tuple[int, int, int, int]) -> Optional[float]:
    """Mean 0–255 luma inside (left, top, right, bottom)."""
    rgb = _as_rgb_float(arr)
    if rgb is None or np is None:
        return None
    left, top, right, bottom = box
    h, w = rgb.shape[:2]
    left = max(0, min(w, int(left)))
    right = max(left, min(w, int(right)))
    top = max(0, min(h, int(top)))
    bottom = max(top, min(h, int(bottom)))
    if right <= left or bottom <= top:
        return None
    region = rgb[top:bottom, left:right]
    return float(np.mean(_to_gray(region)))


def caption_band_needs_scrim(
    arr,
    *,
    y_frac: float = 0.40,
    height_frac: float = 0.12,
    text_rgb: tuple[int, int, int] = (255, 255, 255),
    min_contrast: float = CAPTION_SCRIM_MIN_CONTRAST,
) -> bool:
    """True when caption-band background fails contrast vs text color."""
    rgb = _as_rgb_float(arr)
    if rgb is None or np is None:
        return False
    h, w = rgb.shape[:2]
    band_h = max(8, int(h * height_frac))
    cy = int(h * y_frac)
    top = max(0, cy - band_h // 2)
    bottom = min(h, top + band_h)
    left = int(w * 0.14)
    right = int(w * 0.86)
    mean_luma = region_mean_luma(rgb, (left, top, right, bottom))
    if mean_luma is None:
        return False
    l_bg = _relative_luminance(mean_luma)
    l_text = (
        0.2126 * _relative_luminance(float(text_rgb[0]))
        + 0.7152 * _relative_luminance(float(text_rgb[1]))
        + 0.0722 * _relative_luminance(float(text_rgb[2]))
    )
    return contrast_ratio(l_text, l_bg) < min_contrast


def frame_sharpness_score(arr) -> Optional[float]:
    """Composite score for B-roll window picking: sharpness × local contrast."""
    rgb = _as_rgb_float(arr)
    if rgb is None:
        return None
    sharp = laplacian_variance(rgb)
    if sharp is None:
        return None
    metrics = _contrast_from_rgb_array(rgb)
    contrast = float(metrics.get("contrast_ratio") or 1.0)
    return sharp * max(0.5, contrast)


def audit_product_sharpness(path: Path | str) -> tuple[str, str, str, str]:
    """WARN-only sharpness gate for cached product stills."""
    if Image is None or np is None:
        return "WARN", f">={MIN_PRODUCT_SHARPNESS}", "unavailable", "Could not measure product sharpness."
    path = Path(path)
    if not path.exists():
        return "WARN", f">={MIN_PRODUCT_SHARPNESS}", "missing", "Product still path missing."
    try:
        img = Image.open(path).convert("RGB")
        arr = np.asarray(img, dtype=np.float32)
    except Exception:
        return "WARN", f">={MIN_PRODUCT_SHARPNESS}", "unreadable", "Could not open product still."
    sharp = laplacian_variance(arr)
    if sharp is None:
        return "WARN", f">={MIN_PRODUCT_SHARPNESS}", "unavailable", "Could not measure product sharpness."
    if sharp >= MIN_PRODUCT_SHARPNESS:
        return "PASS", f">={MIN_PRODUCT_SHARPNESS}", f"{sharp:.1f}", "Product still sharpness is acceptable."
    return (
        "WARN",
        f">={MIN_PRODUCT_SHARPNESS}",
        f"{sharp:.1f}",
        "Product still looks soft; hero compositing may skip or look muddy.",
    )


def _contrast_from_rgb_array(arr) -> dict:
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


def measure_pil_contrast(img) -> Optional[dict]:
    if Image is None or np is None or img is None:
        return None
    rgb = img.convert("RGB") if hasattr(img, "convert") else img
    arr = np.asarray(rgb, dtype=np.float32)
    return _contrast_from_rgb_array(arr)


def measure_image_contrast(path: Path | str) -> Optional[dict]:
    if Image is None or np is None:
        return None
    path = Path(path)
    if not path.exists():
        return None
    img = Image.open(path).convert("RGB")
    arr = np.asarray(img, dtype=np.float32)
    return _contrast_from_rgb_array(arr)


def pick_best_contrast_path(paths: list[Path | str]) -> Optional[Path]:
    """Return the path with the highest measured contrast ratio."""
    best: Optional[Path] = None
    best_ratio = -1.0
    for raw in paths:
        path = Path(raw)
        metrics = measure_image_contrast(path)
        if not metrics:
            continue
        ratio = float(metrics.get("contrast_ratio") or 0)
        if ratio > best_ratio:
            best_ratio = ratio
            best = path
    return best


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
