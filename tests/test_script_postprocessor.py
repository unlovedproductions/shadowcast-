import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from script_postprocessor import _apply_kinetic_presets, _repair_truncated_text, enrich_script


PRODUCT = {
    "product_name": "SoundCore Space A40",
    "price": "$79.99",
    "key_features": ["ANC", "50hr battery"],
    "competitors": ["AirPods Pro 2", "Sony WF-1000XM5"],
    "price_comparison": "AirPods Pro 2 costs $249 for similar ANC",
    "comparison_specs": [
        {"spec_name": "ANC", "value_a": "Strong", "value_b": "Moderate", "winner": "a"},
        {"spec_name": "Battery", "value_a": "50hr", "value_b": "30hr", "winner": "a"},
    ],
}


def _short_script():
    return {
        "format": "short_form",
        "segments": [
            {"segment_id": 1, "text": "Hook", "text_style": "headline_bold", "duration": 2},
            {"segment_id": 2, "text": "Bad option", "text_style": "pro_point", "duration": 2},
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
                    {"segment_id": 1, "text": "Worth it for commuters", "text_style": "subtitle", "duration": 3},
                ],
            }
        ],
    }


def test_text_style_alias_normalization():
    enriched = enrich_script(_short_script(), PRODUCT, "honest_review")
    styles = [seg["text_style"] for seg in enriched["segments"]]
    assert "pros" in styles
    assert "pro_point" not in styles


def test_vs_battle_injects_layout_segments():
    enriched = enrich_script(_short_script(), PRODUCT, "vs_battle")
    layouts = [seg.get("layout") for seg in enriched["segments"] if seg.get("layout")]
    assert "vs_split" in layouts
    assert "scorecard" in layouts
    assert "winner_reveal" in layouts


def test_vs_battle_fills_missing_layouts_when_partial():
    partial = {
        "format": "short_form",
        "segments": [
            {"segment_id": 1, "text": "Hook", "text_style": "headline_bold", "duration": 2},
            {
                "segment_id": 2,
                "text": "A vs B",
                "text_style": "comparison",
                "duration": 2,
                "layout": "vs_split",
                "product_a": "SoundCore Space A40",
                "product_b": "AirPods Pro 2",
            },
            {"segment_id": 3, "text": "CTA", "text_style": "cta_button", "duration": 2},
        ],
    }
    enriched = enrich_script(partial, PRODUCT, "vs_battle")
    layouts = {seg.get("layout") for seg in enriched["segments"] if seg.get("layout")}
    assert layouts >= {"vs_split", "scorecard", "winner_reveal"}


def test_elimination_injects_winner_reveal_and_elimination_style():
    enriched = enrich_script(_short_script(), PRODUCT, "elimination")
    styles = [seg.get("text_style") for seg in enriched["segments"]]
    layouts = [seg.get("layout") for seg in enriched["segments"] if seg.get("layout")]
    assert "elimination" in styles
    assert "winner_reveal" in layouts


def test_budget_challenge_injects_price_compare():
    enriched = enrich_script(_short_script(), PRODUCT, "budget_challenge")
    layouts = [seg.get("layout") for seg in enriched["segments"] if seg.get("layout")]
    assert "price_compare" in layouts


def test_worth_it_or_waste_verdict_styling():
    enriched = enrich_script(_long_script(), PRODUCT, "worth_it_or_waste")
    verdict_styles = [
        seg["text_style"]
        for chapter in enriched["chapters"]
        for seg in chapter["segments"]
    ]
    assert verdict_styles[0] == "verdict"


def test_kinetic_presets_clamp_short_form_words_and_duration():
    verbose = {
        "format": "short_form",
        "segments": [
            {
                "segment_id": 1,
                "text": "This is way too many words for a short overlay",
                "text_style": "subtitle",
                "animation": "fade_in",
                "duration": 3.0,
            },
            {
                "segment_id": 2,
                "text": "Still fine here",
                "text_style": "pros",
                "duration": 0.5,
            },
        ],
    }
    _apply_kinetic_presets(verbose)
    first, second = verbose["segments"][0], verbose["segments"][1]
    assert len(first["text"].split()) <= 6
    assert first["duration"] == 1.5
    assert first["text_style"] == "headline_bold"
    assert first["animation"] == "impact_scale"
    assert second["duration"] == 1.0
    assert verbose["total_duration_seconds"] == 2.5


def test_repair_truncated_drops_dangling_preposition():
    assert _repair_truncated_text("Check the current price in") == "Check the current price."
    assert _repair_truncated_text("Does CitrusBurn really work?") == "Does CitrusBurn really work?"


def test_enrich_script_injects_affiliate_disclosure():
    enriched = enrich_script(_short_script(), PRODUCT, "honest_review")
    blob = " ".join(seg["text"] for seg in enriched["segments"])
    styles = [seg["text_style"] for seg in enriched["segments"]]
    assert "affiliate" in blob.lower()
    assert "cta_button" in styles
