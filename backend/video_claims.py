"""Claim registry and helpers for video contract auditing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from content_styles import normalize_content_style


SHORT_FORM = "short_form"
LONG_FORM = "long_form"


@dataclass(frozen=True)
class FormatClaim:
    width: int
    height: int
    fps: int
    min_duration_seconds: float
    max_duration_seconds: float


FORMAT_CLAIMS: dict[str, FormatClaim] = {
    SHORT_FORM: FormatClaim(
        width=1080,
        height=1920,
        fps=30,
        min_duration_seconds=30.0,
        max_duration_seconds=60.0,
    ),
    LONG_FORM: FormatClaim(
        width=1920,
        height=1080,
        fps=30,
        min_duration_seconds=300.0,
        max_duration_seconds=480.0,
    ),
}

# Renderer chrome constants (seconds).
SHORT_INTRO_SECONDS = 2.0
SHORT_OUTRO_SECONDS = 2.0
SHORT_SUBSCRIBE_SECONDS = 2.0

LONG_INTRO_SECONDS = 3.0
LONG_CHAPTER_CARD_SECONDS = 2.5
LONG_COMMENT_PROMPT_SECONDS = 3.0
LONG_SUBSCRIBE_SECONDS = 3.0
LONG_OUTRO_SECONDS = 3.0

SHORT_SUBSCRIBE_THRESHOLD_SEGMENTS = 5

TRANSITION_DURATIONS = {
    "glitch": 0.15,
    "flash": 0.10,
    "swipe": 0.30,
    "zoom": 0.20,
}

REQUIRED_LAYOUTS_BY_STYLE: dict[str, set[str]] = {
    "elimination": {"winner_reveal"},
    "vs_battle": {"vs_split", "scorecard", "winner_reveal"},
    "budget_challenge": {"price_compare"},
}

OPTIONAL_LAYOUTS_BY_STYLE: dict[str, set[str]] = {
    "vs_battle": {"spec_compare"},
}

CLAIMED_ANIMATION_TOKENS = {
    "pop_in",
    "slide_up",
    "slide_left",
    "fade_in",
    "zoom_in",
    "shake",
    "typewriter",
    "bounce",
    "wipe",
}

SUPPORTED_ANIMATION_TOKENS = {
    "word_by_word",
    "typewriter",
    "impact_scale",
    "highlight_sweep",
    "shake",
    "slide_up",
    "slide_left",
    "zoom_in",
    "pop_in",
    "fade_in",
}

CLAIMED_TRANSITION_TOKENS = {
    "cut",
    "whip_pan",
    "fade",
    "zoom_through",
    "glitch",
    "dissolve",
}

SUPPORTED_TRANSITION_TOKENS = {"cut", "fade", "glitch", "flash", "swipe", "zoom"}


def _iter_segments(script: dict, fmt: str) -> list[dict]:
    if fmt == SHORT_FORM:
        return list(script.get("segments", []))
    segments: list[dict] = []
    for chapter in script.get("chapters", []):
        segments.extend(chapter.get("segments", []))
    return segments


def _iter_segment_lists(script: dict, fmt: str) -> list[list[dict]]:
    if fmt == SHORT_FORM:
        return [list(script.get("segments", []))]
    return [list(chapter.get("segments", [])) for chapter in script.get("chapters", [])]


def _segment_duration(segment: dict, default: float) -> float:
    try:
        return float(segment.get("duration", default))
    except (TypeError, ValueError):
        return default


def _transition_duration(segment: dict) -> float:
    token = str(segment.get("transition_to_next", "")).strip().lower()
    return float(TRANSITION_DURATIONS.get(token, 0.0))


def sum_segment_durations(script: dict, fmt: str) -> float:
    default = 2.5 if fmt == SHORT_FORM else 4.0
    return sum(_segment_duration(seg, default) for seg in _iter_segments(script, fmt))


def expected_transition_overhead(script: dict, fmt: str) -> float:
    total = 0.0
    for segment_list in _iter_segment_lists(script, fmt):
        for idx, seg in enumerate(segment_list):
            if idx >= len(segment_list) - 1:
                continue
            total += _transition_duration(seg)
    return total


def expected_timeline_duration(script: dict, fmt: str) -> float:
    segment_seconds = sum_segment_durations(script, fmt)
    transition_seconds = expected_transition_overhead(script, fmt)
    if fmt == SHORT_FORM:
        subscribe = (
            SHORT_SUBSCRIBE_SECONDS
            if len(script.get("segments", [])) > SHORT_SUBSCRIBE_THRESHOLD_SEGMENTS
            else 0.0
        )
        return SHORT_INTRO_SECONDS + segment_seconds + transition_seconds + subscribe + SHORT_OUTRO_SECONDS

    chapters = script.get("chapters", [])
    chapter_cards = float(len(chapters)) * LONG_CHAPTER_CARD_SECONDS
    comment_prompt = LONG_COMMENT_PROMPT_SECONDS if chapters else 0.0
    return (
        LONG_INTRO_SECONDS
        + chapter_cards
        + segment_seconds
        + transition_seconds
        + comment_prompt
        + LONG_SUBSCRIBE_SECONDS
        + LONG_OUTRO_SECONDS
    )


def collect_layouts(script: dict, fmt: str) -> set[str]:
    layouts: set[str] = set()
    for seg in _iter_segments(script, fmt):
        layout = seg.get("layout")
        if layout:
            layouts.add(str(layout))
    return layouts


def missing_required_layouts(style: str, script: dict, fmt: str) -> set[str]:
    normalized = normalize_content_style(style)
    required = REQUIRED_LAYOUTS_BY_STYLE.get(normalized, set())
    layouts = collect_layouts(script, fmt)
    return required - layouts


def missing_optional_layouts(style: str, script: dict, fmt: str, claimed: Iterable[str] | None = None) -> set[str]:
    normalized = normalize_content_style(style)
    optional = OPTIONAL_LAYOUTS_BY_STYLE.get(normalized, set())
    if claimed is not None:
        optional = optional.intersection({str(v) for v in claimed})
    if not optional:
        return set()
    layouts = collect_layouts(script, fmt)
    return optional - layouts


def unsupported_animation_tokens(script: dict, fmt: str) -> set[str]:
    unsupported: set[str] = set()
    for seg in _iter_segments(script, fmt):
        token = str(seg.get("animation", "")).strip().lower()
        if token and token not in SUPPORTED_ANIMATION_TOKENS:
            unsupported.add(token)
    return unsupported


def unsupported_transition_tokens(script: dict, fmt: str) -> set[str]:
    unsupported: set[str] = set()
    for seg in _iter_segments(script, fmt):
        token = str(seg.get("transition_to_next", "")).strip().lower()
        if token and token not in SUPPORTED_TRANSITION_TOKENS:
            unsupported.add(token)
    return unsupported
