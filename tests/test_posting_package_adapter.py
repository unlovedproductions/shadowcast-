"""Tests for posting_package_adapter."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from posting_package_adapter import (  # noqa: E402
    build,
    select_video_format,
    _truncate_youtube_tags,
)


SAMPLE_ASSETS = {
    "seo_title": "Honest Review: Best Widget 2026 — Pros and Cons",
    "seo_description": "A" * 3000,
    "tags": ["widget review", "best widget", "widget 2026", "honest review", "buying guide"],
    "hashtags": ["#widget", "#review", "#honest", "#2026", "#buying"],
    "pinned_comment": "My honest take after testing this widget for 30 days. Great for daily use but noisy at night.",
}


def test_select_video_format_vertical_platforms():
    assert select_video_format("instagram", "long_form") == "short_form"
    assert select_video_format("tiktok", "long_form") == "short_form"
    assert select_video_format("rumble", "long_form") == "short_form"


def test_select_video_format_youtube():
    assert select_video_format("youtube", "short_form") == "short_form"
    assert select_video_format("youtube", "long_form") == "long_form"


def test_youtube_build_includes_shorts_tag():
    payload = build("youtube", SAMPLE_ASSETS, {"format": "short_form"})
    assert payload["platform"] == "youtube"
    assert "#Shorts" in payload["description"]
    assert payload["is_short"] is True
    assert len(payload["title"]) <= 100


def test_instagram_caption_truncation():
    assets = {**SAMPLE_ASSETS, "pinned_comment": "x" * 3000}
    payload = build("instagram", assets)
    assert payload["platform"] == "instagram"
    assert len(payload["caption"]) <= 2200
    assert "#widget" in payload["caption"]


def test_tiktok_title_limit():
    assets = {**SAMPLE_ASSETS, "seo_title": "T" * 200}
    payload = build("tiktok", assets)
    assert len(payload["title"]) <= 150
    assert len(payload["hashtags"]) <= 5


def test_facebook_build():
    payload = build("facebook", SAMPLE_ASSETS)
    assert payload["title"] == SAMPLE_ASSETS["seo_title"]
    assert payload["description"] == SAMPLE_ASSETS["seo_description"]


def test_rumble_tags_limit():
    assets = {**SAMPLE_ASSETS, "tags": [f"tag{i}" for i in range(20)]}
    payload = build("rumble", assets)
    assert len(payload["tags"]) <= 10


def test_youtube_tags_char_limit():
    tags = [f"keyword{i}" for i in range(100)]
    trimmed = _truncate_youtube_tags(tags)
    total = sum(len(t) for t in trimmed) + max(0, len(trimmed) - 1)
    assert total <= 500
