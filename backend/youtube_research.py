"""YouTube keyword / title research (autocomplete + optional Data API)."""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

import httpx

_SUGGEST_URL = "https://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q={query}"
# Full a–z is too chatty (~30 serial calls). Sample vowels + common continuations.
_EXPAND_SUFFIXES = list("aeiou") + [" best", " review", " vs", " 2026", " under"]
_QUESTION_PREFIXES = ("how to", "what is", "best", "vs", "review", "worth it", "does")


async def _fetch_suggestions(query: str, client: httpx.AsyncClient) -> list[str]:
    """Fetch autocomplete suggestions from YouTube Suggest API."""
    url = _SUGGEST_URL.format(query=query)
    try:
        response = await client.get(url, timeout=5.0)
        response.raise_for_status()
        match = re.search(r"window\.google\.ac\.h\((.*)\)", response.text)
        if not match:
            return []
        data = json.loads(match.group(1))
        return [item[0] for item in data[1] if item and item[0]]
    except Exception as exc:
        print(f"YouTube suggest failed for '{query}': {exc}")
        return []


def _title_angles(query: str, questions: list[str], titles: list[str]) -> list[str]:
    angles: list[str] = []
    for q in questions[:6]:
        angles.append(q if len(q) <= 70 else q[:67].rstrip() + "…")
    for t in titles:
        if t not in angles:
            angles.append(t)
        if len(angles) >= 8:
            break
    if not angles:
        angles = [
            f"{query} honest review",
            f"Is {query} worth it?",
            f"{query} vs alternatives",
        ]
    return angles[:8]


def _content_gap_ideas(query: str, questions: list[str]) -> list[str]:
    """Heuristic content-gap angles (Trends Tab substitute without Studio login)."""
    ideas = [
        f"Answer a real search question about {query} in the first 3 seconds",
        f"Cover a comparison gap: {query} vs the usual premium alternative",
        f"Call out who should NOT buy {query} (trust + retention)",
    ]
    for q in questions[:4]:
        ideas.append(f"Content gap angle: {q}")
    return ideas[:6]


async def _optional_data_api_titles(query: str, client: httpx.AsyncClient) -> list[str]:
    """If YOUTUBE_API_KEY is set, pull a few competing video titles via search.list."""
    api_key = (os.getenv("YOUTUBE_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        return []
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "type": "video",
        "maxResults": "5",
        "q": query,
        "key": api_key,
        "relevanceLanguage": "en",
    }
    try:
        response = await client.get(url, params=params, timeout=8.0)
        response.raise_for_status()
        data = response.json()
        titles: list[str] = []
        for item in data.get("items") or []:
            title = ((item.get("snippet") or {}).get("title") or "").strip()
            if title:
                titles.append(title)
        return titles
    except Exception as exc:
        print(f"YouTube Data API search failed for '{query}': {exc}")
        return []


async def research_youtube_keywords(query: str) -> dict[str, Any]:
    """
    YouTube keyword/title research.

    Default path: parallel autocomplete (no API key).
    Optional: YOUTUBE_API_KEY / GOOGLE_API_KEY enables search.list competitor titles.
    """
    query = (query or "").strip()
    if not query:
        return {
            "autocomplete_suggestions": [],
            "long_tail_keywords": [],
            "question_keywords": [],
            "recommended_titles": [],
            "recommended_tags": [],
            "title_angles": [],
            "content_gap_ideas": [],
            "data_api_titles": [],
        }

    async with httpx.AsyncClient() as client:
        base_task = _fetch_suggestions(query, client)
        expand_tasks = [
            _fetch_suggestions(f"{query}{suffix}" if suffix.startswith(" ") else f"{query} {suffix}", client)
            for suffix in _EXPAND_SUFFIXES
        ]
        question_tasks = [
            _fetch_suggestions(f"{prefix} {query}", client) for prefix in _QUESTION_PREFIXES
        ]
        data_api_task = _optional_data_api_titles(query, client)

        results = await asyncio.gather(
            base_task,
            *expand_tasks,
            *question_tasks,
            data_api_task,
            return_exceptions=True,
        )

    def _as_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(v) for v in value if str(v).strip()]
        return []

    autocomplete_suggestions = _as_list(results[0])
    expand_count = len(_EXPAND_SUFFIXES)
    long_tail: set[str] = set()
    for chunk in results[1 : 1 + expand_count]:
        long_tail.update(_as_list(chunk))
    question_keywords: set[str] = set()
    q_start = 1 + expand_count
    for chunk in results[q_start : q_start + len(_QUESTION_PREFIXES)]:
        question_keywords.update(_as_list(chunk))
    data_api_titles = _as_list(results[-1])

    all_suggestions = list(
        dict.fromkeys(
            autocomplete_suggestions + list(long_tail) + list(question_keywords) + data_api_titles
        )
    )

    recommended_titles = all_suggestions[:5]
    if len(recommended_titles) < 5:
        for suggestion in autocomplete_suggestions:
            if suggestion not in recommended_titles:
                recommended_titles.append(suggestion)
            if len(recommended_titles) == 5:
                break
    if not recommended_titles:
        recommended_titles = [f"{query} honest review"]

    recommended_tags = sorted(all_suggestions, key=len)[:20]
    questions = list(question_keywords)
    title_angles = _title_angles(query, questions, recommended_titles + data_api_titles)
    content_gap_ideas = _content_gap_ideas(query, questions)

    return {
        "autocomplete_suggestions": autocomplete_suggestions,
        "long_tail_keywords": list(long_tail),
        "question_keywords": questions,
        "recommended_titles": recommended_titles,
        "recommended_tags": recommended_tags,
        "title_angles": title_angles,
        "content_gap_ideas": content_gap_ideas,
        "data_api_titles": data_api_titles,
    }


if __name__ == "__main__":
    async def main():
        test_query = "wireless earbuds"
        print(f"\nResearching keywords for: '{test_query}'")
        results = await research_youtube_keywords(test_query)
        for key, value in results.items():
            print(f"\n{key}:")
            for item in value[:8]:
                print(f"- {item}")

    asyncio.run(main())
