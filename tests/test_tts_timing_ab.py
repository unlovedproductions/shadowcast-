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
    load_clips,
    main,
    make_mock_generate,
    mock_tts_duration_seconds,
    run_ab,
)


def test_mock_duration_scales_with_words():
    short = mock_tts_duration_seconds("one two")
    long = mock_tts_duration_seconds("one two three four five six seven eight")
    assert long > short


def test_load_clips_rejects_missing_segment_duration(tmp_path):
    fixtures = {
        "clips": [
            {
                "clip_id": "bad_fixture",
                "segments": [{"segment_id": 1, "text": "hello world"}],
            }
        ]
    }
    fixtures_path = tmp_path / "fixtures.json"
    fixtures_path.write_text(json.dumps(fixtures), encoding="utf-8")
    with pytest.raises(ValueError, match="segment 0 missing duration"):
        load_clips(fixtures_path)


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
    assert "clips_without_trim_under_a" in report["summary"]
    assert "total_trim_seconds_under_a" in report["summary"]
    assert all("totals" in c and "segments" in c for c in report["clips"])

    out = tmp_path / "report.json"
    out.write_text(json.dumps(report), encoding="utf-8")
    loaded = json.loads(out.read_text())
    assert loaded["mode"] == "mock"


def test_main_can_fail_ci_guard_when_trim_signal_missing(tmp_path):
    fixtures = {
        "clips": [
            {
                "clip_id": "no_trim_probe",
                "content_style": "honest_review",
                "format": "short_form",
                "segments": [
                    {
                        "segment_id": 1,
                        "text": "short line",
                        "duration": 5.0,
                    }
                ],
            }
        ]
    }
    fixtures_path = tmp_path / "fixtures.json"
    fixtures_path.write_text(json.dumps(fixtures), encoding="utf-8")
    out_path = tmp_path / "ab.json"
    exit_code = main(
        [
            "--fixtures",
            str(fixtures_path),
            "--out",
            str(out_path),
            "--require-trimmed-under-a",
            "1",
        ]
    )
    assert exit_code == 2
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["summary"]["segments_trimmed_under_a"] == 0


def test_main_can_fail_trim_seconds_guard_when_trim_signal_missing(tmp_path):
    fixtures = {
        "clips": [
            {
                "clip_id": "no_trim_probe",
                "content_style": "honest_review",
                "format": "short_form",
                "segments": [
                    {
                        "segment_id": 1,
                        "text": "short line",
                        "duration": 5.0,
                    }
                ],
            }
        ]
    }
    fixtures_path = tmp_path / "fixtures.json"
    fixtures_path.write_text(json.dumps(fixtures), encoding="utf-8")
    out_path = tmp_path / "ab.json"
    exit_code = main(
        [
            "--fixtures",
            str(fixtures_path),
            "--out",
            str(out_path),
            "--require-trim-seconds-under-a",
            "0.1",
        ]
    )
    assert exit_code == 2
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["summary"]["total_trim_seconds_under_a"] == 0.0
