"""Tests for SRT sidecar and publish quality checklist."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from caption_srt import timing_rows_to_srt, write_srt_sidecar  # noqa: E402
from publish_quality import evaluate_publish_quality  # noqa: E402


def test_timing_rows_to_srt_basic():
    rows = [
        {"text": "Hello world", "start": 0.0, "duration": 1.5},
        {"text": "Second line", "start": 1.5, "duration": 2.0},
    ]
    srt = timing_rows_to_srt(rows, intro_offset=1.0)
    assert "00:00:01,000 --> 00:00:02,500" in srt
    assert "Hello world" in srt
    assert "00:00:02,500 --> 00:00:04,500" in srt
    assert "Second line" in srt


def test_write_srt_sidecar(tmp_path):
    video = tmp_path / "demo_long_form.mp4"
    video.write_bytes(b"fake")
    path = write_srt_sidecar(
        video,
        [{"text": "Hook", "start": 0.0, "duration": 1.0}],
        intro_offset=0.5,
    )
    assert path is not None
    out = Path(path)
    assert out.exists()
    assert out.suffix == ".srt"
    assert "Hook" in out.read_text(encoding="utf-8")


def test_evaluate_publish_quality_missing_video(tmp_path):
    with patch("publish_quality.get_best_tts", return_value="kokoro"):
        result = evaluate_publish_quality(
            video_path=tmp_path / "missing.mp4",
            video_format="short_form",
        )
    assert result["overall"] == "FAIL"
    assert result["ready_for_live_publish"] is False
    assert any(c["id"] == "video_exists" and c["status"] == "FAIL" for c in result["checks"])
    assert any(c["id"] == "claim_audit" and c["status"] == "FAIL" for c in result["checks"])


def test_evaluate_publish_quality_pass_path(tmp_path):
    video = tmp_path / "ok_short_form.mp4"
    video.write_bytes(b"x")
    (tmp_path / "ok_short_form.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8")
    with patch("publish_quality.get_best_tts", return_value="kokoro"), patch(
        "publish_quality._ffprobe_duration", return_value=30.0
    ), patch(
        "publish_quality._claim_audit_check",
        return_value={"id": "claim_audit", "status": "PASS", "detail": "ok"},
    ), patch(
        "publish_quality.music_beds_present", return_value=True
    ), patch(
        "publish_quality.music_bed_moods", return_value=["chill"]
    ), patch(
        "publish_quality.any_broll_files", return_value=True
    ):
        result = evaluate_publish_quality(
            video_path=video,
            video_format="short_form",
            image_url="https://example.com/product.jpg",
        )
    assert result["overall"] in ("PASS", "WARN")
    assert result["ready_for_live_publish"] is True
    assert any(c["id"] == "captions_sidecar" and c["status"] == "PASS" for c in result["checks"])
    assert any(c["id"] == "claim_audit" and c["status"] == "PASS" for c in result["checks"])
    assert any(c["id"] == "music_bed" and c["status"] == "PASS" for c in result["checks"])
    assert any(c["id"] == "product_image" and c["status"] == "PASS" for c in result["checks"])


def test_evaluate_publish_quality_fails_without_music_beds(tmp_path, monkeypatch):
    video = tmp_path / "ok_short_form.mp4"
    video.write_bytes(b"x")
    monkeypatch.delenv("ALLOW_SYNTH_MUSIC_PUBLISH", raising=False)
    with patch("publish_quality.get_best_tts", return_value="kokoro"), patch(
        "publish_quality._ffprobe_duration", return_value=30.0
    ), patch(
        "publish_quality._claim_audit_check",
        return_value={"id": "claim_audit", "status": "PASS", "detail": "ok"},
    ), patch(
        "publish_quality.music_beds_present", return_value=False
    ), patch(
        "publish_quality.music_bed_moods", return_value=[]
    ), patch(
        "publish_quality.any_broll_files", return_value=False
    ):
        result = evaluate_publish_quality(video_path=video, video_format="short_form")
    assert result["ready_for_live_publish"] is False
    assert any(c["id"] == "music_bed" and c["status"] == "FAIL" for c in result["checks"])


def test_evaluate_publish_quality_thumb_packaging_warns_on_dense_copy(tmp_path):
    video = tmp_path / "ok_short_form.mp4"
    video.write_bytes(b"x")
    thumb = tmp_path / "ok_short_form_thumb.jpg"
    thumb.write_bytes(b"fakejpg")
    pkg = tmp_path / "ok_short_form_youtube_package.json"
    pkg.write_text(
        '{"seo_title":"Test","thumbnail_text_primary":"one two three four five six seven"}',
        encoding="utf-8",
    )
    with patch("publish_quality.get_best_tts", return_value="kokoro"), patch(
        "publish_quality._ffprobe_duration", return_value=30.0
    ), patch(
        "publish_quality._claim_audit_check",
        return_value={"id": "claim_audit", "status": "PASS", "detail": "ok"},
    ), patch(
        "publish_quality.music_beds_present", return_value=True
    ), patch(
        "publish_quality.music_bed_moods", return_value=["chill"]
    ), patch(
        "publish_quality.any_broll_files", return_value=True
    ), patch(
        "publish_quality.audit_thumbnail_contrast",
        return_value=("PASS", "ok", "ok", "ok"),
    ):
        result = evaluate_publish_quality(
            video_path=video,
            video_format="short_form",
            thumbnail_path=thumb,
            image_url="https://example.com/p.jpg",
        )
    assert any(
        c["id"] == "thumb_packaging" and c["status"] == "WARN" for c in result["checks"]
    )
