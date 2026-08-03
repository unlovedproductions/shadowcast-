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


# Duration windows are wider than prompt targets (short ~30–60s, long ~5–8min) because
# LLM segment sums plus renderer chrome (intro/outro/transitions) routinely fall outside
# tight bands; WARN on duration_window flags outliers, not every sub-target miss.
FORMAT_CLAIMS: dict[str, FormatClaim] = {
    SHORT_FORM: FormatClaim(
        width=1080,
        height=1920,
        fps=30,
        min_duration_seconds=12.0,
        max_duration_seconds=90.0,
    ),
    LONG_FORM: FormatClaim(
        width=1920,
        height=1080,
        fps=30,
        min_duration_seconds=120.0,
        max_duration_seconds=720.0,
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
    "fade": 0.0,
    "cut": 0.0,
}

REQUIRED_LAYOUTS_BY_STYLE: dict[str, set[str]] = {
    "elimination": {"winner_reveal"},
    "vs_battle": {"vs_split", "scorecard", "winner_reveal"},
    "budget_challenge": {"price_compare"},
}

OPTIONAL_LAYOUTS_BY_STYLE: dict[str, set[str]] = {
    "vs_battle": {"spec_compare"},
}

# Must match prompt schema enums in prompts.py (subset of SUPPORTED_*).
CLAIMED_ANIMATION_TOKENS = {
    "pop_in",
    "slide_up",
    "slide_left",
    "fade_in",
    "zoom_in",
    "shake",
    "typewriter",
    "word_by_word",
    "impact_scale",
    "highlight_sweep",
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
    "fade",
    "glitch",
    "flash",
    "swipe",
    "zoom",
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
    return float(build_render_timeline(script, fmt)["total_duration"])


def intro_seconds_for(fmt: str) -> float:
    return SHORT_INTRO_SECONDS if fmt == SHORT_FORM else LONG_INTRO_SECONDS


def build_render_timeline(script: dict, fmt: str) -> dict:
    """
    Single source of truth for visual/audio timing.

    Returns:
      intro_seconds, total_duration,
      segment_events: [{segment, start, duration, transition, transition_duration, transition_at}],
      chrome_events: [{kind, start, duration}]
    """
    segment_events: list[dict] = []
    chrome_events: list[dict] = []

    if fmt == SHORT_FORM:
        t = SHORT_INTRO_SECONDS
        chrome_events.append({"kind": "intro", "start": 0.0, "duration": SHORT_INTRO_SECONDS})
        segments = list(script.get("segments", []))
        for idx, seg in enumerate(segments):
            seg_dur = _segment_duration(seg, 2.5)
            trans_dur = _transition_duration(seg) if idx < len(segments) - 1 else 0.0
            transition = str(seg.get("transition_to_next", "")).strip().lower()
            segment_events.append(
                {
                    "segment": seg,
                    "start": t,
                    "duration": seg_dur,
                    "transition": transition,
                    "transition_duration": trans_dur,
                    "transition_at": t + seg_dur,
                }
            )
            t += seg_dur + trans_dur
        if len(segments) > SHORT_SUBSCRIBE_THRESHOLD_SEGMENTS:
            chrome_events.append({"kind": "subscribe", "start": t, "duration": SHORT_SUBSCRIBE_SECONDS})
            t += SHORT_SUBSCRIBE_SECONDS
        chrome_events.append({"kind": "outro", "start": t, "duration": SHORT_OUTRO_SECONDS})
        t += SHORT_OUTRO_SECONDS
        return {
            "format": SHORT_FORM,
            "intro_seconds": SHORT_INTRO_SECONDS,
            "total_duration": t,
            "segment_events": segment_events,
            "chrome_events": chrome_events,
        }

    t = LONG_INTRO_SECONDS
    chrome_events.append({"kind": "intro", "start": 0.0, "duration": LONG_INTRO_SECONDS})
    chapters = list(script.get("chapters", []))
    engagement_inserted = False
    for ch_idx, chapter in enumerate(chapters):
        chrome_events.append(
            {"kind": "chapter_card", "start": t, "duration": LONG_CHAPTER_CARD_SECONDS, "chapter_index": ch_idx}
        )
        t += LONG_CHAPTER_CARD_SECONDS
        segments = list(chapter.get("segments", []))
        for idx, seg in enumerate(segments):
            seg_dur = _segment_duration(seg, 4.0)
            trans_dur = _transition_duration(seg) if idx < len(segments) - 1 else 0.0
            transition = str(seg.get("transition_to_next", "")).strip().lower()
            segment_events.append(
                {
                    "segment": seg,
                    "start": t,
                    "duration": seg_dur,
                    "transition": transition,
                    "transition_duration": trans_dur,
                    "transition_at": t + seg_dur,
                    "chapter_index": ch_idx,
                }
            )
            t += seg_dur + trans_dur
        if not engagement_inserted and ch_idx >= len(chapters) // 2:
            chrome_events.append({"kind": "comment_prompt", "start": t, "duration": LONG_COMMENT_PROMPT_SECONDS})
            t += LONG_COMMENT_PROMPT_SECONDS
            engagement_inserted = True
    if chapters:
        chrome_events.append({"kind": "subscribe", "start": t, "duration": LONG_SUBSCRIBE_SECONDS})
        t += LONG_SUBSCRIBE_SECONDS
        chrome_events.append({"kind": "outro", "start": t, "duration": LONG_OUTRO_SECONDS})
        t += LONG_OUTRO_SECONDS
    return {
        "format": LONG_FORM,
        "intro_seconds": LONG_INTRO_SECONDS,
        "total_duration": t,
        "segment_events": segment_events,
        "chrome_events": chrome_events,
    }


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
