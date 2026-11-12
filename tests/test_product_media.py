"""Tests for product still helpers."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from product_media import (
    frame_with_product_hero,
    paste_product_hero,
    prepare_product_still,
    segment_wants_product_hero,
    thumbnail_with_product_hero,
)


def test_segment_wants_product_hero_hook_and_layouts():
    assert segment_wants_product_hero({}, segment_index=0) is True
    assert segment_wants_product_hero({"text_style": "subtitle"}, segment_index=1) is False
    assert segment_wants_product_hero({"text_style": "subtitle"}, segment_index=3) is True
    assert segment_wants_product_hero({"layout": "winner_reveal"}, segment_index=5) is True
    assert segment_wants_product_hero({"text_style": "cta_button"}, segment_index=2) is True
    assert segment_wants_product_hero({"text_style": "stat_number"}, segment_index=4) is True


def test_paste_and_thumbnail_hero(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    product = Image.new("RGB", (200, 200), color=(220, 40, 40))
    # Add edge detail so Laplacian variance clears the sharpness gate.
    for x in range(200):
        product.putpixel((x, 100), (10, 10, 10))
        product.putpixel((100, x), (10, 10, 10))
    product_path = tmp_path / "product.png"
    product.save(product_path)

    base = Image.new("RGB", (640, 360), color=(10, 10, 15))
    out = paste_product_hero(base, product.convert("RGBA"), is_short_form=False)
    assert out.size == (640, 360)
    arr = np.array(out.convert("RGB"))
    assert arr[:, :, 0].max() > 100  # red product visible

    thumb = Image.new("RGB", (1280, 720), color=(10, 10, 15))
    hero_thumb = thumbnail_with_product_hero(thumb, product_path)
    assert hero_thumb.size == (1280, 720)

    frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
    framed = frame_with_product_hero(frame, product_path, is_short_form=True)
    assert framed.shape == (1920, 1080, 3)
    assert framed.max() > 0


def test_prepare_crops_toward_padded_subject():
    pytest.importorskip("PIL")
    from PIL import Image

    # Large white pad with a sharp colored subject on the right.
    canvas = Image.new("RGB", (300, 200), color=(250, 250, 250))
    for x in range(180, 260):
        for y in range(40, 160):
            val = (220, 30, 30) if (x + y) % 2 == 0 else (30, 30, 220)
            canvas.putpixel((x, y), val)
    prepared = prepare_product_still(canvas)
    assert prepared is not None
    assert prepared.width < 300
    assert prepared.height <= 200


def test_prepare_rejects_blurry_still():
    pytest.importorskip("PIL")
    from PIL import Image, ImageFilter

    soft = Image.new("RGB", (160, 160), color=(120, 80, 60))
    soft = soft.filter(ImageFilter.GaussianBlur(radius=12))
    assert prepare_product_still(soft) is None

    base = Image.new("RGB", (640, 360), color=(10, 10, 15))
    out = paste_product_hero(base, soft.convert("RGBA"), is_short_form=True)
    # Soft still must not paint a large muddy plate — canvas stays dark.
    arr = np.array(out.convert("RGB"))
    assert float(arr.mean()) < 40.0
