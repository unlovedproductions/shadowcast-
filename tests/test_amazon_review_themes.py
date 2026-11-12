"""Amazon review theme extraction (local NLP)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from amazon_scraper import _extract_review_themes  # noqa: E402


def test_extract_review_themes_from_titles():
    reviews = [
        {"title": "Battery life is incredible", "text": "Lasts all day on ANC."},
        {"title": "Battery life is incredible", "text": "Still going after 8 hours."},
        {"title": "Comfortable for long wear", "text": "No ear fatigue with battery life."},
        {"title": "Comfortable for long wear", "text": "Soft tips, great seal."},
    ]
    themes = _extract_review_themes(reviews)
    assert "Battery life is incredible" in themes
    assert themes.startswith("- ")
    assert "(Requires NLP" not in themes


def test_extract_review_themes_empty():
    assert _extract_review_themes([]) == ""
