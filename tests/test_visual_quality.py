"""Visual quality and thumbnail audit tests."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from visual_quality import audit_thumbnail_contrast, contrast_ratio, measure_image_contrast


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
