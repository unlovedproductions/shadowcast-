"""Automated 6-style × 2-format matrix checks (script layouts + badges)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from content_styles import style_badge_text, normalize_content_style
from script_postprocessor import enrich_script


PRODUCT = {
    "product_name": "SoundCore Space A40",
    "price": "$79.99",
    "key_features": ["ANC", "50hr battery", "IPX4"],
    "competitors": ["AirPods Pro 2", "Sony WF-1000XM5"],
    "price_comparison": "AirPods Pro 2 costs $249 for similar ANC",
    "comparison_specs": [
        {"spec_name": "ANC", "value_a": "Strong", "value_b": "Moderate", "winner": "a"},
        {"spec_name": "Battery", "value_a": "50hr", "value_b": "30hr", "winner": "a"},
    ],
}

STYLES = [
    "honest_review",
    "elimination",
    "vs_battle",
    "budget_challenge",
    "worth_it_or_waste",
    "standard",
]

EXPECTED_LAYOUTS = {
    "elimination": {"winner_reveal"},
    "vs_battle": {"vs_split", "spec_compare", "scorecard", "winner_reveal"},
    "budget_challenge": {"price_compare"},
}

EXPECTED_TEXT_STYLES = {
    "elimination": {"elimination"},
}

EXPECTED_BADGES = {
    "honest_review": "HONEST REVIEW",
    "elimination": "ELIMINATION",
    "vs_battle": "VS BATTLE",
    "budget_challenge": "BUDGET PICK",
    "worth_it_or_waste": "WORTH IT?",
    "standard": None,
}


def _short_script():
    return {
        "format": "short_form",
        "segments": [
            {"segment_id": 1, "text": "Hook", "text_style": "headline_bold", "duration": 2},
            {"segment_id": 2, "text": "Detail", "text_style": "subtitle", "duration": 2},
            {"segment_id": 3, "text": "CTA", "text_style": "cta_button", "duration": 2},
        ],
    }


def _long_script():
    return {
        "format": "long_form",
        "chapters": [
            {
                "chapter_name": "The Verdict",
                "segments": [
                    {"segment_id": 1, "text": "Final take", "text_style": "subtitle", "duration": 3},
                    {"segment_id": 2, "text": "Buy link", "text_style": "cta_button", "duration": 2},
                ],
            }
        ],
    }


def _all_segments(script: dict):
    if "chapters" in script:
        segs = []
        for ch in script["chapters"]:
            segs.extend(ch.get("segments", []))
        return segs
    return script.get("segments", [])


def test_style_badge_matrix():
    for style in STYLES:
        assert style_badge_text(style) == EXPECTED_BADGES[style]


def test_short_form_layout_matrix():
    for style in STYLES:
        enriched = enrich_script(_short_script(), PRODUCT, style)
        segs = _all_segments(enriched)
        layouts = {seg.get("layout") for seg in segs if seg.get("layout")}
        expected = EXPECTED_LAYOUTS.get(style, set())
        assert expected.issubset(layouts), f"{style} short_form missing {expected - layouts}"
        if style in ("honest_review", "standard"):
            assert not layouts, f"{style} short_form should not inject layout segments"
        text_styles = {seg.get("text_style") for seg in segs if seg.get("text_style")}
        for required in EXPECTED_TEXT_STYLES.get(style, set()):
            assert required in text_styles, f"{style} short_form missing text_style {required}"


def test_long_form_layout_and_verdict_matrix():
    for style in STYLES:
        enriched = enrich_script(_long_script(), PRODUCT, style)
        segs = _all_segments(enriched)
        layouts = {seg.get("layout") for seg in segs if seg.get("layout")}
        expected = EXPECTED_LAYOUTS.get(style, set())
        assert expected.issubset(layouts), f"{style} long_form missing {expected - layouts}"
        if style in ("honest_review", "standard"):
            assert not layouts, f"{style} long_form should not inject layout segments"
        text_styles = {seg.get("text_style") for seg in segs if seg.get("text_style")}
        for required in EXPECTED_TEXT_STYLES.get(style, set()):
            assert required in text_styles, f"{style} long_form missing text_style {required}"
        if style == "worth_it_or_waste":
            assert "verdict" in text_styles, f"{style} long_form missing text_style verdict"


def test_normalize_round_trip_aliases():
    assert normalize_content_style("elimination_round") == "elimination"
    assert normalize_content_style("standard_promo") == "standard"
