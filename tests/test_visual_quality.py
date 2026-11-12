"""Visual quality and thumbnail audit tests."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from visual_quality import (
    MIN_WCAG_CONTRAST,
    audit_thumbnail_contrast,
    caption_band_needs_scrim,
    contrast_ratio,
    energy_bbox,
    laplacian_variance,
    measure_image_contrast,
    measure_pil_contrast,
    pick_best_contrast_path,
    studio_bg_mask,
)


def test_contrast_ratio_symmetry():
    assert contrast_ratio(0.2, 0.8) == pytest.approx(contrast_ratio(0.8, 0.2))


def test_audit_thumbnail_contrast_missing_file(tmp_path):
    missing = tmp_path / "missing_thumbnail_a.png"
    severity, expected, actual, detail = audit_thumbnail_contrast(missing)
    assert severity == "WARN"
    assert "Could not measure" in detail


def test_measure_image_contrast_on_generated_png(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    path = tmp_path / "sample_thumbnail_a.png"
    img = Image.new("RGB", (320, 180), color=(20, 20, 20))
    for x in range(40, 280):
        for y in range(60, 120):
            img.putpixel((x, y), (240, 240, 240))
    img.save(path)

    metrics = measure_image_contrast(path)
    assert metrics is not None
    assert metrics["contrast_ratio"] >= 4.5
    severity, _, actual, _ = audit_thumbnail_contrast(path)
    assert severity == "PASS"
    assert ":1" in actual


def test_text_only_thumbnail_meets_wcag_contrast(tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("numpy")
    from thumbnail_generator import generate_thumbnail, select_best_contrast_variant

    variants = {
        "variant_a": generate_thumbnail(
            title="Mito Formula",
            subtitle="$79.95 | Worth It?",
            style="bold_text",
        ),
        "variant_b": generate_thumbnail(
            title="Worth It?",
            subtitle="$79.95",
            style="split",
        ),
        "variant_c": generate_thumbnail(
            title="$79",
            subtitle="Honest Review",
            style="number",
        ),
    }
    best_key = select_best_contrast_variant(variants)
    best = variants[best_key]
    metrics = measure_pil_contrast(best)
    assert metrics is not None
    assert metrics["contrast_ratio"] >= MIN_WCAG_CONTRAST

    out = tmp_path / f"thumb_{best_key}.png"
    best.save(out)
    severity, _, _, _ = audit_thumbnail_contrast(out)
    assert severity == "PASS"


def test_pick_best_contrast_path(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    low = tmp_path / "low.png"
    high = tmp_path / "high.png"
    Image.new("RGB", (100, 100), color=(40, 40, 40)).save(low)
    img = Image.new("RGB", (100, 100), color=(10, 10, 10))
    for x in range(20, 80):
        for y in range(20, 80):
            img.putpixel((x, y), (250, 250, 250))
    img.save(high)
    assert pick_best_contrast_path([low, high]) == high


def test_laplacian_variance_sharp_vs_blurred():
    pytest.importorskip("PIL")
    pytest.importorskip("numpy")
    import numpy as np
    from PIL import Image, ImageFilter

    sharp = Image.new("RGB", (128, 128), color=(20, 20, 20))
    for x in range(40, 90):
        for y in range(40, 90):
            sharp.putpixel((x, y), (240, 40, 40) if (x + y) % 2 == 0 else (40, 40, 240))
    blurred = sharp.filter(ImageFilter.GaussianBlur(radius=6))
    s_sharp = laplacian_variance(np.asarray(sharp, dtype=np.float32))
    s_blur = laplacian_variance(np.asarray(blurred, dtype=np.float32))
    assert s_sharp is not None and s_blur is not None
    assert s_sharp > s_blur * 2


def test_energy_bbox_on_offset_square():
    pytest.importorskip("numpy")
    import numpy as np

    arr = np.zeros((100, 100, 3), dtype=np.float32)
    arr[20:50, 55:85] = 255.0
    box = energy_bbox(arr, percentile=85, pad=0.02)
    assert box is not None
    left, top, right, bottom = box
    assert left >= 40  # subject is on the right half
    assert right > 70
    assert top < 40
    assert bottom > 40


def test_studio_bg_mask_white_canvas_dark_center():
    pytest.importorskip("numpy")
    import numpy as np

    arr = np.full((120, 120, 3), 245.0, dtype=np.float32)
    arr[40:80, 40:80] = 40.0
    mask = studio_bg_mask(arr)
    assert mask is not None
    assert float(mask[60, 60]) > float(mask[5, 5])


def test_studio_bg_mask_skips_white_on_white():
    pytest.importorskip("numpy")
    import numpy as np

    arr = np.full((120, 120, 3), 245.0, dtype=np.float32)
    arr[40:80, 40:80] = 235.0  # nearly white product
    assert studio_bg_mask(arr) is None


def test_caption_band_needs_scrim_on_bright_band():
    pytest.importorskip("numpy")
    import numpy as np

    dark = np.full((200, 108, 3), 10.0, dtype=np.float32)
    bright = np.full((200, 108, 3), 10.0, dtype=np.float32)
    # Shorts caption band ~ y_frac 0.40
    y0, y1 = 60, 100
    bright[y0:y1, :] = 230.0
    assert caption_band_needs_scrim(dark, y_frac=0.40) is False
    assert caption_band_needs_scrim(bright, y_frac=0.40) is True
