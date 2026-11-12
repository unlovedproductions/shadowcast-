"""Unit tests for Shorts burn-in caption chunking and TTS-clock placement."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brand_overlays import (
    SHORTS_CAPTION_MAX_WORDS,
    SHORTS_CAPTION_MIN_WORDS,
    SHORTS_CAPTION_Y_FRAC,
    SHORTS_LOWER_THIRD_BOTTOM_FRAC,
    SHORTS_WORD_HIGHLIGHT_MIN_SEC,
    caption_events_from_timing,
    chunk_caption_text,
    displayable_price,
    expand_caption_word_highlights,
    longform_burnin_captions_enabled,
    lower_third_event_from_timing,
    render_lower_third,
    render_shorts_caption,
    render_subscribe_card,
    render_watermark_overlay,
    shorts_burnin_captions_enabled,
    shorts_word_highlight_enabled,
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


def test_expand_caption_word_highlights_proportional_timing():
    chunk = {
        "text": "one two three four five",
        "start": 1.0,
        "duration": 1.0,
        "segment_index": 0,
    }
    words = expand_caption_word_highlights([chunk], enabled=True)
    assert len(words) == 5
    assert [w["highlight_index"] for w in words] == list(range(5))
    assert all(w["text"] == chunk["text"] for w in words)
    assert words[0]["start"] == pytest.approx(1.0)
    assert words[-1]["start"] + words[-1]["duration"] == pytest.approx(2.0)
    assert sum(w["duration"] for w in words) == pytest.approx(1.0)
    assert all(w["duration"] == pytest.approx(0.2) for w in words)


def test_expand_caption_word_highlights_skips_when_too_brief_or_disabled():
    brief = {
        "text": "one two three four",
        "start": 0.0,
        "duration": SHORTS_WORD_HIGHLIGHT_MIN_SEC * 3,  # 4 words → under min
        "segment_index": 1,
    }
    skipped = expand_caption_word_highlights([brief], enabled=True)
    assert len(skipped) == 1
    assert skipped[0]["highlight_index"] is None
    assert skipped[0]["duration"] == pytest.approx(brief["duration"])

    disabled = expand_caption_word_highlights(
        [{"text": "one two three four", "start": 0.0, "duration": 2.0}],
        enabled=False,
    )
    assert len(disabled) == 1
    assert disabled[0]["highlight_index"] is None


def test_shorts_word_highlight_env_gate(monkeypatch):
    monkeypatch.delenv("SHADOWCAST_SHORTS_WORD_HIGHLIGHT", raising=False)
    assert shorts_word_highlight_enabled() is True
    monkeypatch.setenv("SHADOWCAST_SHORTS_WORD_HIGHLIGHT", "0")
    assert shorts_word_highlight_enabled() is False
    monkeypatch.setenv("SHADOWCAST_SHORTS_WORD_HIGHLIGHT", "true")
    assert shorts_word_highlight_enabled() is True


def test_burnin_captions_default_off(monkeypatch):
    monkeypatch.delenv("SHADOWCAST_SHORTS_BURNIN", raising=False)
    monkeypatch.delenv("SHADOWCAST_LONGFORM_BURNIN", raising=False)
    assert shorts_burnin_captions_enabled() is False
    assert longform_burnin_captions_enabled() is False
    monkeypatch.setenv("SHADOWCAST_SHORTS_BURNIN", "1")
    monkeypatch.setenv("SHADOWCAST_LONGFORM_BURNIN", "1")
    assert shorts_burnin_captions_enabled() is True
    assert longform_burnin_captions_enabled() is True


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


def test_render_shorts_caption_with_highlight_index():
    plain = render_shorts_caption(1080, 1920, "one two three four")
    hi = render_shorts_caption(1080, 1920, "one two three four", highlight_index=1)
    assert hi.size == plain.size
    assert list(hi.getdata()) != list(plain.getdata())


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


def test_lower_third_event_triggers_on_first_product_mention():
    timing = [
        {
            "index": 0,
            "text": "stop wasting money on junk",
            "start": 0.0,
            "tts_duration": 1.0,
            "duration": 1.35,
        },
        {
            "index": 1,
            "text": "the Super Product X actually lasts",
            "start": 1.35,
            "tts_duration": 2.0,
            "duration": 2.35,
        },
    ]
    # "Super Product X" starts at word index 1 of 6 → (1/6)*speech into seg1
    # intro 2.0 + 1.35 + (1/6)*2.0 - lead 0.3
    ev = lower_third_event_from_timing(
        timing, "Super Product X", intro_offset=2.0, hold_sec=5.5, mention_lead=0.3
    )
    assert ev is not None
    assert ev["duration"] == pytest.approx(5.5)
    expected_start = 2.0 + 1.35 + (1 / 6) * 2.0 - 0.3
    assert ev["start"] == pytest.approx(round(expected_start, 3))


def test_lower_third_event_fallback_and_clamp():
    timing = [
        {
            "index": 0,
            "text": "no brand here at all",
            "start": 0.5,
            "tts_duration": 1.0,
            "duration": 1.35,
        }
    ]
    ev = lower_third_event_from_timing(
        timing, "Acme Widget", intro_offset=2.0, hold_sec=5.5, mention_lead=0.3
    )
    assert ev is not None
    # No mention → first speech start − lead
    assert ev["start"] == pytest.approx(2.2)  # 2.0 + 0.5 - 0.3
    clamped = lower_third_event_from_timing(
        timing,
        "Acme Widget",
        intro_offset=2.0,
        hold_sec=5.5,
        mention_lead=0.0,
        video_duration=3.0,
    )
    assert clamped is not None
    assert clamped["start"] == pytest.approx(2.5)
    assert clamped["duration"] == pytest.approx(0.5)


def test_shorts_lower_third_above_caption_band():
    """Shorts LT sits near bottom UI; captions remain mid-upper (no Y competition)."""
    assert SHORTS_LOWER_THIRD_BOTTOM_FRAC > 0.8
    assert SHORTS_CAPTION_Y_FRAC < 0.5
    img = render_lower_third(1080, 1920, "Mini Product Y", "Free", is_short_form=True)
    assert img.size == (1080, 1920)
    # Opaque pixels should exist in the raised bar band, not flush at y=height-1.
    bar_bottom = int(1920 * SHORTS_LOWER_THIRD_BOTTOM_FRAC)
    px_bottom_edge = img.getpixel((540, 1919))
    px_bar = img.getpixel((540, bar_bottom - 10))
    assert px_bottom_edge[3] == 0
    assert px_bar[3] > 0


def test_displayable_price_hides_placeholders():
    assert displayable_price("Varies") == ""
    assert displayable_price("see official offer page") == ""
    assert displayable_price("$29.99") == "$29.99"
    assert displayable_price("Free") == "Free"
    img = render_lower_third(1080, 1920, "CitrusBurn", "Varies", is_short_form=True)
    bar_bottom = int(1920 * SHORTS_LOWER_THIRD_BOTTOM_FRAC)
    # Price side of the bar should not contain extra glyphs for 'Varies'
    assert img.size == (1080, 1920)
    assert img.getpixel((540, bar_bottom - 10))[3] > 0


def test_watermark_is_inset_and_small():
    img = render_watermark_overlay(1080, 1920)
    opaque = [
        (x, y)
        for y in range(0, 1920, 4)
        for x in range(0, 1080, 8)
        if img.getpixel((x, y))[3] > 0
    ]
    assert opaque
    max_x = max(p[0] for p in opaque)
    max_y = max(p[1] for p in opaque)
    min_x = min(p[0] for p in opaque)
    assert max_x < 1080 - int(1080 * 0.03)
    assert max_y < 1920 - int(1920 * 0.03)
    assert max_y - min(p[1] for p in opaque) < 1920 * 0.08
    assert min_x > 1080 * 0.7


def test_subscribe_card_tagline_fits_shorts_card():
    arr = render_subscribe_card(1080, 1920)
    assert arr.shape[1] == 1080
    assert arr.shape[0] == 1920
    # Card interior should not be clipped: sample right edge of canvas is background
    edge = tuple(int(v) for v in arr[960, 1070][:3])
    assert edge[0] < 40 and edge[1] < 40 and edge[2] < 40
