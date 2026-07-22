"""Video claim audit tests."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from script_postprocessor import enrich_script
from video_claim_audit import (
    _expected_output_counts,
    _validate_youtube_package,
    audit_output,
)
from video_claims import (
    CLAIMED_ANIMATION_TOKENS,
    CLAIMED_TRANSITION_TOKENS,
    FORMAT_CLAIMS,
    LONG_FORM,
    SHORT_FORM,
    SUPPORTED_ANIMATION_TOKENS,
    SUPPORTED_TRANSITION_TOKENS,
    expected_timeline_duration,
    missing_required_layouts,
    unsupported_animation_tokens,
    unsupported_transition_tokens,
)


def test_format_claim_registry_contract():
    short = FORMAT_CLAIMS[SHORT_FORM]
    long = FORMAT_CLAIMS[LONG_FORM]
    assert (short.width, short.height, short.fps) == (1080, 1920, 30)
    assert (long.width, long.height, long.fps) == (1920, 1080, 30)
    assert (short.min_duration_seconds, short.max_duration_seconds) == (12.0, 90.0)
    assert (long.min_duration_seconds, long.max_duration_seconds) == (120.0, 720.0)


def test_expected_timeline_duration_short_form():
    script = {
        "format": SHORT_FORM,
        "segments": [
            {"duration": 2.0, "transition_to_next": "glitch"},
            {"duration": 2.0, "transition_to_next": "fade"},
            {"duration": 2.0, "transition_to_next": "swipe"},
            {"duration": 2.0, "transition_to_next": "zoom"},
            {"duration": 2.0, "transition_to_next": "cut"},
            {"duration": 2.0},
        ],
    }
    assert expected_timeline_duration(script, SHORT_FORM) == pytest.approx(18.65, abs=0.01)


def test_expected_timeline_duration_long_form():
    script = {
        "format": LONG_FORM,
        "chapters": [
            {
                "chapter_name": "A",
                "segments": [
                    {"duration": 4.0, "transition_to_next": "glitch"},
                    {"duration": 4.0},
                ],
            },
            {
                "chapter_name": "B",
                "segments": [
                    {"duration": 4.0, "transition_to_next": "swipe"},
                    {"duration": 4.0},
                ],
            },
        ],
    }
    assert expected_timeline_duration(script, LONG_FORM) == pytest.approx(33.45, abs=0.01)


def test_style_required_layouts_align_with_enrichment():
    product = {
        "product_name": "SoundCore Space A40",
        "price": "$79.99",
        "competitors": ["AirPods Pro 2"],
        "price_comparison": "$79.99 vs $249",
        "comparison_specs": [
            {"spec_name": "ANC", "value_a": "Strong", "value_b": "Strong", "winner": "none"},
            {"spec_name": "Battery", "value_a": "50h", "value_b": "30h", "winner": "a"},
            {"spec_name": "Comfort", "value_a": "Great", "value_b": "Good", "winner": "a"},
        ],
    }
    base_short = {
        "format": SHORT_FORM,
        "segments": [
            {"segment_id": 1, "text": "Hook", "text_style": "headline_bold", "duration": 2.0},
            {"segment_id": 2, "text": "Detail", "text_style": "subtitle", "duration": 2.0},
            {"segment_id": 3, "text": "CTA", "text_style": "cta_button", "duration": 2.0},
        ],
    }
    for style in ("elimination", "vs_battle", "budget_challenge"):
        enriched = enrich_script(base_short, product, style)
        missing = missing_required_layouts(style, enriched, SHORT_FORM)
        assert not missing, f"{style} missing required layouts: {missing}"


def test_unsupported_token_detection():
    script = {
        "format": SHORT_FORM,
        "segments": [
            {"duration": 2.0, "animation": "bounce", "transition_to_next": "whip_pan"},
            {"duration": 2.0, "animation": "fade_in", "transition_to_next": "glitch"},
        ],
    }
    assert unsupported_animation_tokens(script, SHORT_FORM) == {"bounce"}
    assert unsupported_transition_tokens(script, SHORT_FORM) == {"whip_pan"}
    assert (CLAIMED_ANIMATION_TOKENS - SUPPORTED_ANIMATION_TOKENS) >= {"bounce", "wipe"}
    assert (CLAIMED_TRANSITION_TOKENS - SUPPORTED_TRANSITION_TOKENS) >= {"whip_pan", "zoom_through", "dissolve"}


def test_expected_output_counts_from_job():
    single = {"hook_types": ["curiosity", "honest_review"], "formats": ["short_form", "long_form"]}
    assert _expected_output_counts(single) == (4, 4)
    batch = {
        "mode": "batch",
        "hook_types": ["curiosity"],
        "formats": ["short_form"],
        "products": [{}, {}, {}],
    }
    assert _expected_output_counts(batch) == (3, 3)
    assert _expected_output_counts({"hook_types": [], "formats": ["short_form"]}) is None


def test_validate_youtube_package_rejects_stub(tmp_path):
    stub = tmp_path / "pkg.json"
    stub.write_text(json.dumps({"seo_title": "Title", "tags": ["a"] * 5, "_shadowcast_fallback": True}))
    ok, detail = _validate_youtube_package(stub)
    assert not ok
    assert "stub" in detail

    valid = tmp_path / "valid.json"
    valid.write_text(json.dumps({"seo_title": "Real Title", "tags": ["a", "b", "c", "d", "e"]}))
    ok, detail = _validate_youtube_package(valid)
    assert ok, detail


def test_audit_deliverables_warn_on_missing_posting_txt(tmp_path):
    job_dir = tmp_path / "job1"
    job_dir.mkdir()
    (job_dir / "job.json").write_text(
        json.dumps({"hook_types": ["curiosity"], "formats": ["short_form"], "mode": "single"})
    )
    (job_dir / "demo_curiosity_short.mp4").write_bytes(b"fake")
    result = audit_output(tmp_path)
    checks = {item["check"] for item in result["findings"]}
    assert "posting_package_txt" in checks
    assert "youtube_package_json" in checks


def test_live_output_has_no_fail_findings_when_present():
    output_dir = Path(__file__).resolve().parents[1] / "backend" / "output"
    result = audit_output(output_dir)
    if result["videos_checked"] == 0:
        pytest.skip("No rendered MP4 artifacts in backend/output")
    assert result["fail_count"] == 0, result["findings"]
