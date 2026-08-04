"""Unit tests for audio-driven TTS timing and loudnorm helpers."""

from __future__ import annotations

import json
import os
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from sound_design import SAMPLE_RATE, _cosine_duck_envelope, apply_two_pass_loudnorm, mix_audio
from tts_generator import (
    apply_timing_to_script,
    generate_voiceover_for_segments,
)


def _write_silence_wav(path: str, duration_s: float, rate: int = 24000) -> None:
    n = max(1, int(duration_s * rate))
    frames = (np.zeros(n, dtype=np.int16)).tobytes()
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(frames)


def test_audio_driven_sets_duration_from_speech_plus_pause(tmp_path, monkeypatch):
    monkeypatch.setenv("SHADOWCAST_TTS_INTER_SEGMENT_PAUSE", "0.35")

    durations = [0.80, 1.20]

    def fake_generate(text, output_path, provider="auto", voice=None):
        # Alternate fixed lengths by call order via text length heuristic
        dur = durations[0] if "first" in text else durations[1]
        _write_silence_wav(output_path, dur)
        return output_path

    segments = [
        {"text": "first line here", "duration": 1.0},
        {"text": "second line longer", "duration": 1.0},
    ]
    out = str(tmp_path / "vo.mp3")

    with patch("tts_generator.generate_segment_audio", side_effect=fake_generate):
        path, timing = generate_voiceover_for_segments(
            segments, out, provider="gtts", audio_driven=True, apply_durations=True
        )

    assert path == out
    assert len(timing) == 2
    assert timing[0]["tts_duration"] == pytest.approx(0.80, abs=0.05)
    assert timing[0]["duration"] == pytest.approx(1.15, abs=0.05)
    assert segments[0]["duration"] == pytest.approx(1.15, abs=0.05)
    # Must not trim speech below measured TTS length
    assert segments[0]["duration"] >= segments[0]["tts_duration"]
    assert segments[1]["duration"] > 1.0  # grew past LLM guess

    sidecar = Path(out).with_name("vo_timing.json")
    assert sidecar.exists()
    data = json.loads(sidecar.read_text())
    assert data["total_duration_seconds"] == pytest.approx(
        sum(r["duration"] for r in timing), abs=0.01
    )


def test_legacy_mode_can_trim_to_llm_slot(tmp_path, monkeypatch):
    monkeypatch.setenv("SHADOWCAST_TTS_INTER_SEGMENT_PAUSE", "0.08")

    def fake_generate(text, output_path, provider="auto", voice=None):
        _write_silence_wav(output_path, 2.0)
        return output_path

    segments = [{"text": "long speech", "duration": 1.0}]
    out = str(tmp_path / "legacy.mp3")

    with patch("tts_generator.generate_segment_audio", side_effect=fake_generate):
        _path, timing = generate_voiceover_for_segments(
            segments, out, provider="gtts", audio_driven=False, apply_durations=False
        )

    assert timing[0]["tts_duration"] <= 1.0 + 1e-6


def test_apply_timing_to_script_updates_total():
    script = {
        "format": "short_form",
        "segments": [
            {"text": "a", "duration": 1.0},
            {"text": "b", "duration": 1.0},
        ],
    }
    timing = [
        {"index": 0, "tts_duration": 0.5, "pause": 0.35, "duration": 0.85, "start": 0.0, "text": "a"},
        {"index": 1, "tts_duration": 0.7, "pause": 0.35, "duration": 1.05, "start": 0.85, "text": "b"},
    ]
    apply_timing_to_script(script, timing)
    assert script["total_duration_seconds"] == pytest.approx(1.9)
    assert script["segments"][0]["tts_duration"] == 0.5
    assert "tts_timing" in script


def test_cosine_duck_envelope_ramps():
    presence = np.zeros(1000)
    presence[200:800] = 1.0
    env = _cosine_duck_envelope(presence, duck_factor=0.55, ramp_samples=50)
    assert env[0] == pytest.approx(1.0, abs=0.05)
    assert env[500] == pytest.approx(0.55, abs=0.08)
    # Should not be a hard step at the boundary
    assert env[200] > 0.55


def test_mix_audio_loudnorm_optional(tmp_path):
    bg = np.zeros(SAMPLE_RATE)  # 1s silence-ish
    bg[1000:2000] = 0.2
    vo = np.zeros(SAMPLE_RATE // 2)
    vo[100:400] = 0.5
    out = str(tmp_path / "mix.wav")
    mix_audio(bg, [], voiceover_array=vo, output_path=out, apply_loudnorm=False)
    assert os.path.exists(out) and os.path.getsize(out) > 0

    # loudnorm path should not raise even if ffmpeg missing/fails
    apply_two_pass_loudnorm(out)
    assert os.path.exists(out)
