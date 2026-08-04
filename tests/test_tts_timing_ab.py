"""Unit tests for the TTS timing A/B harness (mock TTS only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from eval.tts_timing_ab import (
    DEFAULT_CLIPS,
    compare_clip,
    make_mock_generate,
    mock_tts_duration_seconds,
    run_ab,
)


def test_mock_duration_scales_with_words():
    short = mock_tts_duration_seconds("one two")
    long = mock_tts_duration_seconds("one two three four five six seven eight")
    assert long > short


def test_harness_detects_trim_vs_pad(tmp_path, monkeypatch):
    monkeypatch.setenv("SHADOWCAST_TTS_INTER_SEGMENT_PAUSE", "0.35")
    # Force speech longer than LLM slot so A must trim.
    fake = make_mock_generate(words_per_sec=1.5)
    script = {
        "clip_id": "trim_probe",
        "content_style": "honest_review",
        "format": "short_form",
        "segments": [
            {
                "segment_id": 1,
                "text": "This long line will exceed the tight LLM duration slot easily",
                "duration": 0.9,
            },
            {
                "segment_id": 2,
                "text": "Second line also oversized for the legacy trim path",
                "duration": 0.85,
            },
        ],
    }
    result = compare_clip(
        script,
        work_dir=tmp_path / "trim_probe",
        live=False,
        mock_generate=fake,
    )
    assert result["totals"]["segments_trimmed_a"] >= 1
    assert result["totals"]["length_delta_b_minus_a"] > 0
    for seg in result["segments"]:
        if seg["speech_trimmed_a"]:
            assert seg["tts_duration_a"] < seg["tts_duration_b"]
            assert seg["trim_seconds_a"] > 0
            assert seg["final_duration_b"] >= seg["tts_duration_b"]


def test_run_ab_default_five_clips_writes_report_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("SHADOWCAST_TTS_INTER_SEGMENT_PAUSE", "0.35")
    assert len(DEFAULT_CLIPS) == 5
    report = run_ab(
        DEFAULT_CLIPS[:2],  # keep unit test cheap
        live=False,
        work_dir=tmp_path / "ab",
        mock_generate=make_mock_generate(words_per_sec=2.0),
    )
    assert report["experiment"] == "tts_timing_ab"
    assert report["clip_count"] == 2
    assert "segments_trimmed_under_a" in report["summary"]
    assert all("totals" in c and "segments" in c for c in report["clips"])

    out = tmp_path / "report.json"
    out.write_text(json.dumps(report), encoding="utf-8")
    loaded = json.loads(out.read_text())
    assert loaded["mode"] == "mock"
