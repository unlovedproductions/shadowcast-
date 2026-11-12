"""Focused tests for video render timeline, audio mux, and cache fingerprinting."""

import json
import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sound_design import SAMPLE_RATE, add_audio_to_video, mix_audio
from video_claims import (
    LONG_FORM,
    SHORT_FORM,
    build_render_timeline,
    expected_timeline_duration,
)
from video_renderer import (
    compute_render_fingerprint,
    fingerprint_seed,
)


def test_build_render_timeline_short_includes_transitions():
    script = {
        "format": SHORT_FORM,
        "segments": [
            {"duration": 2.0, "transition_to_next": "glitch", "animation": "fade_in"},
            {"duration": 2.0, "transition_to_next": "swipe", "animation": "slide_up"},
            {"duration": 2.0},
        ],
    }
    timeline = build_render_timeline(script, SHORT_FORM)
    assert timeline["intro_seconds"] == 2.0
    assert timeline["segment_events"][0]["start"] == pytest.approx(2.0)
    # first transition (glitch 0.15) pushes second segment start
    assert timeline["segment_events"][1]["start"] == pytest.approx(4.15)
    assert timeline["segment_events"][0]["transition_duration"] == pytest.approx(0.15)
    assert timeline["total_duration"] == pytest.approx(expected_timeline_duration(script, SHORT_FORM))


def test_build_render_timeline_long_sfx_offsets_include_chapter_cards():
    script = {
        "format": LONG_FORM,
        "chapters": [
            {
                "chapter_name": "A",
                "segments": [
                    {"duration": 4.0, "transition_to_next": "glitch"},
                    {"duration": 4.0},
                ],
            },
            {
                "chapter_name": "B",
                "segments": [
                    {"duration": 4.0, "transition_to_next": "swipe"},
                    {"duration": 4.0},
                ],
            },
        ],
    }
    timeline = build_render_timeline(script, LONG_FORM)
    # intro 3 + chapter card 2.5 = first segment at 5.5
    assert timeline["segment_events"][0]["start"] == pytest.approx(5.5)
    # after seg0(4)+glitch(0.15) = 9.65
    assert timeline["segment_events"][1]["start"] == pytest.approx(9.65)
    assert timeline["total_duration"] == pytest.approx(33.45, abs=0.01)


def test_mix_audio_voiceover_respects_intro_offset(tmp_path):
    duration_s = 4.0
    bg = np.zeros(int(duration_s * SAMPLE_RATE), dtype=np.float64)
    voice = np.ones(int(1.0 * SAMPLE_RATE), dtype=np.float64) * 0.5
    out = tmp_path / "mix.wav"
    mix_audio(bg, [], voiceover_array=voice, output_path=str(out), voiceover_start_seconds=2.0)

    from scipy.io.wavfile import read as read_wav

    rate, data = read_wav(str(out))
    assert rate == SAMPLE_RATE
    arr = data.astype(np.float64) / 32767.0
    # silence before offset
    assert np.max(np.abs(arr[: int(1.9 * SAMPLE_RATE)])) < 0.05
    # voice present after offset
    window = arr[int(2.0 * SAMPLE_RATE) : int(2.5 * SAMPLE_RATE)]
    assert np.max(np.abs(window)) > 0.1


def test_add_audio_to_video_raises_on_ffmpeg_failure(tmp_path):
    video = tmp_path / "v.mp4"
    audio = tmp_path / "a.wav"
    out = tmp_path / "out.mp4"
    video.write_bytes(b"not-a-video")
    audio.write_bytes(b"not-audio")

    with mock.patch("sound_design.subprocess.run", side_effect=FileNotFoundError("ffmpeg")):
        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            add_audio_to_video(str(video), str(audio), str(out))


def test_add_audio_to_video_raises_on_called_process_error(tmp_path):
    video = tmp_path / "v.mp4"
    audio = tmp_path / "a.wav"
    out = tmp_path / "out.mp4"
    video.write_bytes(b"x")
    audio.write_bytes(b"y")

    err = mock.Mock()
    err.stdout = b""
    err.stderr = b"mux failed"
    with mock.patch(
        "sound_design.subprocess.run",
        side_effect=__import__("subprocess").CalledProcessError(1, "ffmpeg", stderr=b"mux failed"),
    ):
        with pytest.raises(RuntimeError, match="ffmpeg mux failed"):
            add_audio_to_video(str(video), str(audio), str(out))


def test_compute_render_fingerprint_changes_with_script_and_options():
    script_a = {"segments": [{"text": "A", "duration": 2}]}
    script_b = {"segments": [{"text": "B", "duration": 2}]}
    opts = {"video_preset": "medium", "use_tts": False}
    fa = compute_render_fingerprint(script_a, fmt="short_form", render_options=opts)
    fb = compute_render_fingerprint(script_b, fmt="short_form", render_options=opts)
    fc = compute_render_fingerprint(
        script_a, fmt="short_form", render_options={**opts, "use_tts": True}
    )
    assert fa != fb
    assert fa != fc
    assert fingerprint_seed(fa) == fingerprint_seed(fa)


def test_video_cache_ok_requires_matching_fingerprint(tmp_path, monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    import app as app_mod

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00" * 64)
    fingerprint = "abc123"

    monkeypatch.setattr(app_mod, "_artifact_ok", lambda path, *a, **k: True)
    assert app_mod._video_cache_ok(video, fingerprint) is False

    app_mod._write_video_render_meta(video, fingerprint, {"video_preset": "medium"})
    assert app_mod._video_cache_ok(video, fingerprint) is True
    assert app_mod._video_cache_ok(video, "other") is False


def test_build_segment_clip_returns_layout_frame():
    from video_renderer import build_segment_clip, BRAND_ACCENT, BRAND_BG

    seg = {
        "text": "Winner",
        "duration": 1.0,
        "layout": "winner_reveal",
        "winner_name": "Product X",
        "animation": "fade_in",
    }
    clip, frame = build_segment_clip(seg, 320, 180, False, BRAND_ACCENT, BRAND_BG)
    assert frame.shape == (180, 320, 3)
    assert float(clip.duration) == pytest.approx(1.0)
    clip.close()
