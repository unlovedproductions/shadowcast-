import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
EVAL = BACKEND / "eval"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(EVAL))

from content_styles import normalize_content_style
from export_snapshots import export_all
from output_validators import check_buyer_language, validate_script_output, validate_youtube_assets
from prompts import (
    BUYER_FOCUS_RULES,
    BUYER_SEO_RULES,
    HOOK_DESCRIPTIONS,
    build_script_user_prompt,
    build_youtube_assets_user_prompt,
    render_full_prompt,
)
from script_postprocessor import enrich_script

PRODUCT = {
    "product_name": "SoundCore Space A40",
    "price": "$79.99",
    "key_features": ["ANC", "50hr battery"],
    "competitors": ["AirPods Pro 2"],
    "affiliate_link": "https://example.com/a40",
    "content_style": "honest_review",
}


def test_hook_descriptions_are_trimmed():
    for desc in HOOK_DESCRIPTIONS.values():
        assert "Example:" not in desc
        assert len(desc) < 120


def test_build_script_user_prompt_non_empty():
    user = build_script_user_prompt(PRODUCT, "curiosity", "honest_review", "short_form")
    assert "SoundCore Space A40" in user
    assert "OUTPUT JSON SCHEMA" in user
    assert "NOT affiliate marketers" not in user
    assert "RENDERER CONTRACT" in user
    assert "total_duration_seconds must equal the sum of segment durations" in user
    assert "TTS-safe" in user
    assert '"layout"' in user
    assert "slide_left" in user
    assert "Include emoji strategically" not in user
    schema = user.split("OUTPUT JSON SCHEMA")[1]
    assert "visual_note" not in schema
    assert "pros|cons" in schema


def test_buyer_rules_in_system_prompt():
    from prompts import SCRIPT_SYSTEM_PROMPT, YOUTUBE_ASSETS_SYSTEM_PROMPT

    assert "NOT affiliate marketers" in SCRIPT_SYSTEM_PROMPT
    assert BUYER_FOCUS_RULES.strip() in SCRIPT_SYSTEM_PROMPT
    assert "commission rates" in YOUTUBE_ASSETS_SYSTEM_PROMPT
    assert BUYER_SEO_RULES.strip() in YOUTUBE_ASSETS_SYSTEM_PROMPT


def test_build_youtube_assets_user_prompt():
    script = {"hook_type": "curiosity", "content_style": "honest_review", "title_suggestion": "Review"}
    user = build_youtube_assets_user_prompt(
        PRODUCT, script, "long_form",
        script_context="Hook | Cons | Verdict",
        cons_lines="Fit issues",
        cta_lines="Check link",
        verdict_lines="Worth it",
    )
    assert "SoundCore Space A40" in user
    assert "Fit issues" in user


def test_render_full_prompt():
    full = render_full_prompt("system line", "user line")
    assert "=== SYSTEM ===" in full
    assert "=== USER ===" in full


def test_export_snapshots_writes_files(tmp_path):
    paths = export_all(tmp_path)
    assert len(paths) == 4
    for p in paths:
        assert p.stat().st_size > 100


def test_validate_script_honest_review_short():
    script = {
        "hook_type": "curiosity",
        "content_style": "honest_review",
        "format": "short_form",
        "title_suggestion": "Review",
        "segments": [
            {"segment_id": 1, "text": "Hook", "text_style": "headline_bold"},
            {"segment_id": 2, "text": "Bad fit", "text_style": "cons"},
            {"segment_id": 3, "text": "CTA", "text_style": "cta_button"},
        ],
    }
    ok, errors = validate_script_output(script, "honest_review", "short_form")
    assert ok, errors


def test_validate_script_rejects_duration_mismatch():
    script = {
        "hook_type": "curiosity",
        "content_style": "honest_review",
        "format": "short_form",
        "title_suggestion": "Review",
        "total_duration_seconds": 40,
        "segments": [
            {"segment_id": 1, "text": "Hook", "text_style": "headline_bold", "duration": 1.2},
            {"segment_id": 2, "text": "Bad fit", "text_style": "cons", "duration": 1.2},
            {"segment_id": 3, "text": "CTA", "text_style": "cta_button", "duration": 1.2},
        ],
    }
    ok, errors = validate_script_output(script, "honest_review", "short_form")
    assert not ok
    assert any("total_duration_seconds" in e for e in errors)


def test_validate_script_rejects_unsupported_animation():
    script = {
        "hook_type": "curiosity",
        "content_style": "honest_review",
        "format": "short_form",
        "title_suggestion": "Review",
        "segments": [
            {"segment_id": 1, "text": "Hook", "text_style": "headline_bold", "animation": "bounce"},
            {"segment_id": 2, "text": "Bad fit", "text_style": "cons"},
            {"segment_id": 3, "text": "CTA", "text_style": "cta_button"},
        ],
    }
    ok, errors = validate_script_output(script, "honest_review", "short_form")
    assert not ok
    assert any("unsupported animation" in e for e in errors)


def test_validate_vs_battle_requires_full_layout_set():
    script = {
        "hook_type": "comparison_trap",
        "content_style": "vs_battle",
        "format": "short_form",
        "title_suggestion": "Vs",
        "segments": [
            {"segment_id": 1, "text": "Hook", "text_style": "headline_bold", "layout": "vs_split"},
            {"segment_id": 2, "text": "Mid", "text_style": "subtitle"},
            {"segment_id": 3, "text": "CTA", "text_style": "cta_button"},
        ],
    }
    ok, errors = validate_script_output(script, "vs_battle", "short_form")
    assert not ok
    assert any("scorecard" in e and "winner_reveal" in e for e in errors)


def test_validate_script_rejects_commission_language():
    script = {
        "hook_type": "curiosity",
        "content_style": "standard",
        "format": "short_form",
        "title_suggestion": "Review",
        "segments": [
            {"segment_id": 1, "text": "Great commission rate", "text_style": "headline_bold"},
            {"segment_id": 2, "text": "Buy", "text_style": "cta_button"},
            {"segment_id": 3, "text": "Now", "text_style": "subtitle"},
        ],
    }
    ok, errors = validate_script_output(script, "standard", "short_form")
    assert not ok
    assert any("affiliate" in e for e in errors)


def test_validate_youtube_assets():
    assets = {
        "seo_title": "SoundCore A40 Honest Review",
        "tags": ["a", "b", "c", "d", "e"],
        "pinned_comment": "Link: https://example.com/a40",
    }
    ok, errors = validate_youtube_assets(assets, "https://example.com/a40")
    assert ok, errors


def test_check_buyer_language_banned():
    assert check_buyer_language("Earn as an affiliate with high EPC")


def test_enriched_script_passes_vs_battle_validator():
    short = {
        "format": "short_form",
        "hook_type": "comparison_trap",
        "content_style": "vs_battle",
        "title_suggestion": "Vs",
        "segments": [{"segment_id": 1, "text": "Hook", "text_style": "headline_bold", "duration": 2}],
    }
    enriched = enrich_script(short, PRODUCT, "vs_battle")
    ok, errors = validate_script_output(enriched, "vs_battle", "short_form")
    assert ok, errors


def test_eval_set_fixture_loads():
    spec = json.loads((EVAL / "fixtures" / "eval_set.json").read_text())
    assert len(spec["cases"]) >= 12


@pytest.mark.llm
@pytest.mark.skipif(not __import__("os").environ.get("LLM_EVAL"), reason="Set LLM_EVAL=1 to run live LLM eval")
def test_live_eval_smoke_hr_short():
    from eval_runner import run_eval

    spec = json.loads((EVAL / "fixtures" / "eval_set.json").read_text())
    cases = [c for c in spec["cases"] if c["id"] == "hr_short"]
    report = run_eval(cases, live=True)
    assert report["passed"] >= 1
