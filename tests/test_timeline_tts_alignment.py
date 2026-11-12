"""Unit tests: TTS/caption clock aligns with build_render_timeline transitions."""

from __future__ import annotations

import wave
from unittest.mock import patch

import numpy as np
import pytest

from brand_overlays import caption_events_from_timing
from tts_generator import (
    chrome_gaps_for_script,
    generate_voiceover_for_segments,
    generate_voiceover_for_script,
    leading_chrome_for_script,
    transition_gaps_for_script,
)
from video_claims import (
    LONG_CHAPTER_CARD_SECONDS,
    LONG_COMMENT_PROMPT_SECONDS,
    SHORT_FORM,
    LONG_FORM,
    build_render_timeline,
)


def _write_silence_wav(path: str, duration_s: float, rate: int = 24000) -> None:
    n = max(1, int(duration_s * rate))
    frames = (np.zeros(n, dtype=np.int16)).tobytes()
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(frames)


def test_tts_starts_match_segment_events_with_transitions(tmp_path, monkeypatch):
    monkeypatch.setenv("SHADOWCAST_TTS_INTER_SEGMENT_PAUSE", "0.35")

    speech = [0.80, 1.00, 0.60]

    def fake_generate(text, output_path, provider="auto", voice=None, **_kwargs):
        idx = 0 if "one" in text else (1 if "two" in text else 2)
        _write_silence_wav(output_path, speech[idx])
        return output_path

    segments = [
        {"text": "one hook line here", "duration": 1.0, "transition_to_next": "glitch"},
        {"text": "two proof beats", "duration": 1.0, "transition_to_next": "swipe"},
        {"text": "three close", "duration": 1.0, "transition_to_next": "fade"},
    ]
    out = str(tmp_path / "vo.mp3")

    with patch("tts_generator.generate_segment_audio", side_effect=fake_generate):
        _path, timing = generate_voiceover_for_segments(
            segments, out, provider="gtts", audio_driven=True, apply_durations=True
        )

    assert timing[0]["transition_duration"] == pytest.approx(0.0)
    assert timing[1]["transition_duration"] == pytest.approx(0.30)
    assert timing[2]["transition_duration"] == pytest.approx(0.0)
    # Segment visual duration must NOT include transition (renderer adds it separately).
    assert segments[0]["duration"] == pytest.approx(timing[0]["duration"])
    assert timing[0]["duration"] == pytest.approx(speech[0] + 0.35, abs=0.05)
    assert timing[1]["start"] == pytest.approx(
        timing[0]["duration"] + timing[0]["transition_duration"], abs=0.05
    )

    script = {"format": SHORT_FORM, "segments": segments, "tts_timing": timing}
    timeline = build_render_timeline(script, SHORT_FORM)
    intro = float(timeline["intro_seconds"])
    for row, event in zip(timing, timeline["segment_events"]):
        assert intro + float(row["start"]) == pytest.approx(float(event["start"]), abs=0.05)
        assert float(row["duration"]) == pytest.approx(float(event["duration"]), abs=0.05)

    # Captions inherit the same starts (plus intro).
    caps = caption_events_from_timing(timing, intro_offset=intro)
    first_by_seg = {}
    for ev in caps:
        first_by_seg.setdefault(ev["segment_index"], ev)
    assert first_by_seg[0]["start"] == pytest.approx(intro, abs=0.05)
    assert first_by_seg[1]["start"] == pytest.approx(
        intro + timing[1]["start"], abs=0.05
    )


def test_long_form_no_false_transition_between_chapters():
    script = {
        "format": LONG_FORM,
        "chapters": [
            {
                "chapter_name": "Pros",
                "segments": [
                    {"text": "a", "transition_to_next": "glitch"},
                    {"text": "b", "transition_to_next": "swipe"},
                ],
            },
            {
                "chapter_name": "Cons",
                "segments": [
                    {"text": "c", "transition_to_next": "zoom"},
                    {"text": "d"},
                ],
            },
        ],
    }
    gaps = transition_gaps_for_script(script)
    assert gaps == pytest.approx([0.0, 0.0, 0.20, 0.0])
    # Chapter card before ch1 + comment prompt after mid chapter (ch_idx=1).
    assert leading_chrome_for_script(script) == pytest.approx(LONG_CHAPTER_CARD_SECONDS)
    assert chrome_gaps_for_script(script) == pytest.approx(
        [
            0.0,
            LONG_CHAPTER_CARD_SECONDS,
            0.0,
            LONG_COMMENT_PROMPT_SECONDS,
        ]
    )


def test_generate_voiceover_for_script_uses_chapter_local_gaps(tmp_path, monkeypatch):
    monkeypatch.setenv("SHADOWCAST_TTS_INTER_SEGMENT_PAUSE", "0.35")

    def fake_generate(text, output_path, provider="auto", voice=None, **_kwargs):
        _write_silence_wav(output_path, 0.5)
        return output_path

    script = {
        "hook_type": "curiosity",
        "format": LONG_FORM,
        "chapters": [
            {
                "chapter_name": "A",
                "segments": [
                    {"text": "first", "transition_to_next": "glitch"},
                    {"text": "second", "transition_to_next": "swipe"},
                ],
            },
            {
                "chapter_name": "B",
                "segments": [
                    {"text": "third", "transition_to_next": "zoom"},
                ],
            },
        ],
    }
    with patch("tts_generator.generate_segment_audio", side_effect=fake_generate):
        _path, timing = generate_voiceover_for_script(script, str(tmp_path), provider="gtts")

    assert timing[0]["transition_duration"] == pytest.approx(0.0)
    assert timing[1]["transition_duration"] == pytest.approx(0.0)  # chapter boundary
    assert timing[2]["transition_duration"] == pytest.approx(0.0)
    assert timing[0]["start"] == pytest.approx(LONG_CHAPTER_CARD_SECONDS, abs=0.05)
    assert timing[1]["chrome_duration"] == pytest.approx(LONG_CHAPTER_CARD_SECONDS)
    assert timing[1]["start"] == pytest.approx(
        timing[0]["start"] + timing[0]["duration"] + 0.0, abs=0.05
    )
    # Next chapter after chapter-card chrome (not swipe 0.30).
    assert timing[2]["start"] == pytest.approx(
        timing[1]["start"] + timing[1]["duration"] + LONG_CHAPTER_CARD_SECONDS, abs=0.05
    )
    # Mid engagement after last chapter (ch_idx >= len//2).
    assert timing[2]["chrome_duration"] == pytest.approx(LONG_COMMENT_PROMPT_SECONDS)


def test_long_form_tts_starts_match_segment_events_with_chrome(tmp_path, monkeypatch):
    monkeypatch.setenv("SHADOWCAST_TTS_INTER_SEGMENT_PAUSE", "0.35")

    def fake_generate(text, output_path, provider="auto", voice=None, **_kwargs):
        _write_silence_wav(output_path, 0.6)
        return output_path

    script = {
        "hook_type": "curiosity",
        "format": LONG_FORM,
        "chapters": [
            {
                "chapter_name": "A",
                "segments": [
                    {"text": "alpha one", "transition_to_next": "glitch"},
                    {"text": "alpha two", "transition_to_next": "fade"},
                ],
            },
            {
                "chapter_name": "B",
                "segments": [
                    {"text": "beta one", "transition_to_next": "zoom"},
                    {"text": "beta two"},
                ],
            },
        ],
    }
    with patch("tts_generator.generate_segment_audio", side_effect=fake_generate):
        _path, timing = generate_voiceover_for_script(script, str(tmp_path), provider="gtts")

    timeline = build_render_timeline(script, LONG_FORM)
    intro = float(timeline["intro_seconds"])
    assert len(timing) == len(timeline["segment_events"])
    for row, event in zip(timing, timeline["segment_events"]):
        assert intro + float(row["start"]) == pytest.approx(float(event["start"]), abs=0.05)
        assert float(row["duration"]) == pytest.approx(float(event["duration"]), abs=0.05)

    chrome_kinds = {c["kind"] for c in timeline["chrome_events"]}
    assert "chapter_card" in chrome_kinds
    assert "comment_prompt" in chrome_kinds
