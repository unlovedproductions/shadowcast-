"""Unit tests for Shorts burn-in caption chunking and TTS-clock placement."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brand_overlays import (
    SHORTS_CAPTION_MAX_WORDS,
    SHORTS_CAPTION_MIN_WORDS,
    SHORTS_CAPTION_Y_FRAC,
    caption_events_from_timing,
    chunk_caption_text,
    render_shorts_caption,
)
from tts_generator import resolve_tts_timing


def test_chunk_caption_text_respects_4_to_7_words():
    short = chunk_caption_text("This changes everything today")
    assert short == ["This changes everything today"]
    assert SHORTS_CAPTION_MIN_WORDS <= len(short[0].split()) <= SHORTS_CAPTION_MAX_WORDS

    long = (
        "This is a longer voiceover line that should split into several "
        "readable caption chunks for muted Shorts viewing"
    )
    chunks = chunk_caption_text(long)
    assert len(chunks) >= 2
    for chunk in chunks:
        n = len(chunk.split())
        assert SHORTS_CAPTION_MIN_WORDS <= n <= SHORTS_CAPTION_MAX_WORDS, chunk


def test_chunk_caption_text_empty_and_merge_tail():
    assert chunk_caption_text("") == []
    assert chunk_caption_text("   ") == []
    # 9 words → prefer not leaving a 2-word orphan
    chunks = chunk_caption_text("one two three four five six seven eight nine")
    assert all(
        SHORTS_CAPTION_MIN_WORDS <= len(c.split()) <= SHORTS_CAPTION_MAX_WORDS
        for c in chunks
    )
    assert sum(len(c.split()) for c in chunks) == 9


def test_caption_events_follow_tts_timing_and_intro_offset():
    timing = [
        {
            "index": 0,
            "text": "one two three four five six seven eight",
            "start": 0.0,
            "tts_duration": 1.0,
            "pause": 0.35,
            "duration": 1.35,
        },
        {
            "index": 1,
            "text": "short hook line here",
            "start": 1.35,
            "tts_duration": 0.8,
            "pause": 0.35,
            "duration": 1.15,
        },
    ]
    events = caption_events_from_timing(timing, intro_offset=2.0)
    assert events
    assert events[0]["start"] == pytest.approx(2.0)
    # First segment has 8 words → two chunks of 4; speech window subdivided
    first_seg = [e for e in events if e["segment_index"] == 0]
    assert len(first_seg) == 2
    assert all(4 <= len(e["text"].split()) <= 7 for e in first_seg)
    assert sum(e["duration"] for e in first_seg) == pytest.approx(1.0)
    # Second segment starts after intro + timing.start
    second = [e for e in events if e["segment_index"] == 1]
    assert second[0]["start"] == pytest.approx(3.35)


def test_render_shorts_caption_ui_safe_zone():
    img = render_shorts_caption(1080, 1920, "muted viewers still read this")
    assert img.size == (1080, 1920)
    assert img.mode == "RGBA"
    # Opaque pixels should exist and cluster near upper-middle band
    pixels = img.load()
    ys = []
    for y in range(0, 1920, 4):
        for x in range(0, 1080, 8):
            if pixels[x, y][3] > 0:
                ys.append(y)
    assert ys
    mid = sorted(ys)[len(ys) // 2]
    assert int(1920 * 0.30) <= mid <= int(1920 * 0.55)
    # Band center target
    assert abs(mid / 1920 - SHORTS_CAPTION_Y_FRAC) < 0.12


def test_resolve_tts_timing_prefers_script_then_sidecar(tmp_path):
    script = {"hook_type": "curiosity", "format": "short_form", "tts_timing": [{"index": 0}]}
    assert resolve_tts_timing(script)[0]["index"] == 0

    script2 = {"hook_type": "curiosity", "format": "short_form"}
    vo = tmp_path / "curiosity_short_form_voiceover.mp3"
    vo.write_bytes(b"")
    sidecar = Path(str(vo.with_suffix("")) + "_timing.json")
    sidecar.write_text(json.dumps({"segments": [{"index": 1, "text": "hi", "start": 0.0}]}))
    rows = resolve_tts_timing(script2, str(vo))
    assert rows[0]["index"] == 1
    assert script2["tts_timing"][0]["index"] == 1
