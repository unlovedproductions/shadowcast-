"""Tests for optional WhisperX align helpers (no whisperx install required)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from whisperx_align import (  # noqa: E402
    align_words_to_audio,
    refine_caption_events_with_word_align,
    whisperx_align_enabled,
)


def test_whisperx_align_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SHADOWCAST_WHISPERX_ALIGN", raising=False)
    assert whisperx_align_enabled() is False
    assert align_words_to_audio("/tmp/nope.wav", "hello") is None


def test_refine_caption_events_with_word_align():
    chunks = [
        {"text": "hello world today", "start": 2.0, "duration": 1.5, "segment_index": 0},
    ]
    words = [
        {"word": "hello", "start": 0.0, "end": 0.4},
        {"word": "world", "start": 0.4, "end": 0.9},
        {"word": "today", "start": 0.9, "end": 1.4},
    ]
    out = refine_caption_events_with_word_align(chunks, words, intro_offset=2.0)
    assert out is not None
    assert len(out) == 3
    assert out[0]["highlight_index"] == 0
    assert out[0]["start"] == 2.0
    assert out[1]["highlight_index"] == 1
    assert out[2]["text"] == "hello world today"


def test_refine_returns_none_when_sparse():
    chunks = [{"text": "one two three four", "start": 0.0, "duration": 2.0}]
    words = [{"word": "one", "start": 0.0, "end": 0.2}]
    assert refine_caption_events_with_word_align(chunks, words) is None


def test_align_words_skips_when_flag_on_but_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv("SHADOWCAST_WHISPERX_ALIGN", "1")
    assert align_words_to_audio(str(tmp_path / "missing.wav"), "hi") is None
