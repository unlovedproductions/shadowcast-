"""Style-rules RAG retrieval and prompt injection tests."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from prompts import build_script_user_prompt
from style_rules_retrieval import (
    STYLE_RULES_RAG_ENABLED,
    attach_style_rules_context,
    build_style_rules_query,
    retrieve_style_rules,
)


def test_retrieve_buyer_language_bans():
    hits = retrieve_style_rules("honest_review", "short_form", "curiosity")
    sources = {hit["source"] for hit in hits}
    assert "BUYER_LANGUAGE_RULES" in sources or "AUDIT" in sources


def test_attach_respects_disable_flag(monkeypatch):
    monkeypatch.setenv("STYLE_RULES_RAG", "0")
    import style_rules_retrieval as srr

    monkeypatch.setattr(srr, "STYLE_RULES_RAG_ENABLED", False)
    product = {"product_name": "Test Widget", "key_features": ["a"]}
    enriched = attach_style_rules_context(product, "honest_review", "short_form", "curiosity")
    assert "_style_rules_context" not in enriched


def test_build_script_user_prompt_includes_block():
    product = {
        "product_name": "Test Widget",
        "key_features": ["feature"],
        "content_style": "honest_review",
        "_style_rules_context": [
            {"source": "BUYER_LANGUAGE_RULES", "text": "Never mention commission rates.", "score": 0.9}
        ],
    }
    prompt = build_script_user_prompt(product, "curiosity", "honest_review", "short_form")
    assert "STYLE RULES" in prompt
    assert "BUYER_LANGUAGE_RULES" in prompt
    assert "commission rates" in prompt


def test_vs_battle_query_includes_layout_terms():
    query = build_style_rules_query("vs_battle", "short_form", "comparison_trap")
    lowered = query.lower()
    assert "vs_split" in lowered or "layout" in lowered
    assert "vs_battle" in lowered or "vs battle" in lowered


def test_style_rules_rag_enabled_by_default():
    assert STYLE_RULES_RAG_ENABLED is True
