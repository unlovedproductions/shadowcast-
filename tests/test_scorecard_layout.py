"""Scorecard layout normalization (winner vs score_a/score_b)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from comparison_layouts import normalize_scorecard_row, render_scorecard  # noqa: E402


def test_normalize_scorecard_row_numeric():
    assert normalize_scorecard_row({"category": "Value", "score_a": 8, "score_b": 5}) == (
        "Value",
        8,
        5,
    )


def test_normalize_scorecard_row_winner_a():
    assert normalize_scorecard_row({"category": "Taste", "winner": "a"}) == ("Taste", 9, 6)


def test_normalize_scorecard_row_winner_b():
    assert normalize_scorecard_row({"category": "Price", "winner": "b"}) == ("Price", 6, 9)


def test_normalize_scorecard_row_winner_none():
    assert normalize_scorecard_row({"category": "Tie", "winner": "none"}) == ("Tie", 7, 7)


def test_normalize_scorecard_row_skips_non_dict():
    assert normalize_scorecard_row("bad") is None  # type: ignore[arg-type]


def test_render_scorecard_accepts_winner_only_rows():
    frame = render_scorecard(
        640,
        360,
        "Product A",
        "Product B",
        [{"category": "Value", "winner": "a"}, {"category": "Support", "winner": "b"}],
    )
    assert frame.shape == (360, 640, 3)


def test_render_scorecard_accepts_numeric_rows():
    frame = render_scorecard(
        640,
        360,
        "Product A",
        "Product B",
        [{"category": "Value", "score_a": 9, "score_b": 4}],
    )
    assert frame.shape == (360, 640, 3)
