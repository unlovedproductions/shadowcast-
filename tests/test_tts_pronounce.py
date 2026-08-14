"""TTS pronunciation prep (plain-text lexicon)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from tts_pronounce import (  # noqa: E402
    expand_inline_skus,
    prepare_tts_text,
    sku_token_to_speakable,
    strip_ssml_to_speakable,
)


def test_strip_ssml_sub_alias():
    raw = 'Buy the <sub alias="A forty">A40</sub> today'
    assert strip_ssml_to_speakable(raw) == "Buy the A forty today"


def test_sku_token_spacing():
    assert sku_token_to_speakable("A40") == "A 40"
    assert "1000" in expand_inline_skus("WF-1000XM5")


def test_prepare_tts_text_aliases_and_product(monkeypatch):
    monkeypatch.delenv("SHADOWCAST_TTS_PRONUNCIATIONS", raising=False)
    out = prepare_tts_text(
        "Is the Space A40 worth it?",
        provider="kokoro",
        product_names=["SoundCore Space A40"],
        aliases={"worth it": "worth it"},
    )
    assert "A 40" in out
    assert "<" not in out


def test_prepare_tts_text_env_aliases(monkeypatch):
    monkeypatch.setenv(
        "SHADOWCAST_TTS_PRONUNCIATIONS",
        '{"XM5":"X M five"}',
    )
    out = prepare_tts_text("Sony XM5 ANC", provider="gtts")
    assert "X M five" in out
