"""YouTube research shape + render fail-fast helpers."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import _script_ready_for_render  # noqa: E402
from youtube_research import research_youtube_keywords  # noqa: E402


def test_script_ready_for_render_rejects_empty():
    ok, detail = _script_ready_for_render({"format": "short_form", "segments": []})
    assert ok is False
    assert "no segments" in detail

    ok, detail = _script_ready_for_render(
        {"format": "short_form", "segments": [{"text": "  "}]}
    )
    assert ok is False
    assert "empty text" in detail

    ok, detail = _script_ready_for_render(
        {"format": "short_form", "segments": [{"text": "Hook now"}]}
    )
    assert ok is True
    assert detail == ""


def test_script_ready_for_render_rejects_short_long_form():
    ok, detail = _script_ready_for_render(
        {
            "format": "long_form",
            "chapters": [
                {"chapter_name": "A", "segments": [{"text": "Hook", "duration": 4.0}]},
                {"chapter_name": "B", "segments": [{"text": "Body", "duration": 4.0}]},
                {"chapter_name": "C", "segments": [{"text": "CTA", "duration": 4.0}]},
            ],
        }
    )
    assert ok is False
    assert "120" in detail


def test_research_youtube_keywords_includes_angles(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    async def _fake_suggest(query: str, client) -> list[str]:
        if query.startswith("best "):
            return [f"best {query[5:]} under 50"]
        return [query, f"{query} review", f"is {query} worth it"]

    with patch("youtube_research._fetch_suggestions", side_effect=_fake_suggest), patch(
        "youtube_research._optional_data_api_titles",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = asyncio.run(research_youtube_keywords("space a40"))

    assert result["title_angles"]
    assert result["content_gap_ideas"]
    assert "data_api_titles" in result
    assert any("review" in t.lower() or "worth" in t.lower() for t in result["title_angles"])
