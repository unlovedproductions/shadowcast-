"""Tests for product still helpers."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from product_media import (
    frame_with_product_hero,
    paste_product_hero,
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
