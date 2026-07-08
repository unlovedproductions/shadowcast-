import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from content_styles import (
    normalize_content_style,
    style_badge_text,
    style_requires_competitors,
    human_style_name,
    DEFAULT_CONTENT_STYLE,
)


def test_normalize_aliases():
    assert normalize_content_style("elimination_round") == "elimination"
    assert normalize_content_style("trust_first_review") == "honest_review"
    assert normalize_content_style("standard_promo") == "standard"
    assert normalize_content_style("unknown_style") == DEFAULT_CONTENT_STYLE
    assert normalize_content_style("") == DEFAULT_CONTENT_STYLE


def test_badge_text():
    assert style_badge_text("honest_review") == "HONEST REVIEW"
    assert style_badge_text("elimination_round") == "ELIMINATION"
    assert style_badge_text("standard") is None


def test_competitor_requirement():
    assert style_requires_competitors("vs_battle") is True
    assert style_requires_competitors("elimination") is True
    assert style_requires_competitors("honest_review") is False


def test_human_style_name():
    assert "Honest Review" in human_style_name("trust_first_review")
    assert "VS Battle" in human_style_name("vs_battle")
