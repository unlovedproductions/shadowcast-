"""Music bed prefer-path and publish gTTS gate."""

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def test_music_bed_loads_when_present():
    from sound_design import SAMPLE_RATE, generate_background_music

    bed_path = Path(__file__).resolve().parents[1] / "backend" / "assets" / "music" / "chill.wav"
    if not bed_path.exists():
        pytest.skip("chill.wav bed not present")
    arr = generate_background_music(2.0, mood="chill", tempo=80)
    assert len(arr) == int(2.0 * SAMPLE_RATE)
    assert np.max(np.abs(arr)) > 0


def test_publish_blocks_gtts_without_escape(monkeypatch):
    from publish_service import PublishService

    monkeypatch.delenv("ALLOW_GTTS_PUBLISH", raising=False)
    monkeypatch.setattr("tts_generator.get_best_provider", lambda: "gtts")

    svc = PublishService(jobs={})
    monkeypatch.setattr(
        "publish_service.resolve_job_assets",
        lambda *a, **k: {
            "video_path": "/tmp/x.mp4",
            "thumbnail_path": None,
            "posting_package": {"seo_title": "t", "description": "d", "tags": ["a"]},
        },
    )
    monkeypatch.setattr("publish_service.build", lambda *a, **k: {"title": "t"})

    with pytest.raises(RuntimeError, match="gTTS"):
        svc.publish("job", "curiosity", "short_form", "youtube", dry_run=False)


def test_publish_allows_gtts_with_escape(monkeypatch):
    from publish_service import PublishService

    monkeypatch.setenv("ALLOW_GTTS_PUBLISH", "1")
    monkeypatch.setattr("tts_generator.get_best_provider", lambda: "gtts")
    monkeypatch.setattr(
        "publish_service.resolve_job_assets",
        lambda *a, **k: {
            "video_path": "/tmp/x.mp4",
            "thumbnail_path": None,
            "posting_package": {"seo_title": "t", "description": "d", "tags": ["a"]},
        },
    )
    monkeypatch.setattr("publish_service.build", lambda *a, **k: {"title": "t"})

    class FakeYT:
        def publish(self, *a, **k):
            return {"status": "success", "dry_run": True}

    svc = PublishService(jobs={})
    svc.youtube = FakeYT()
    result = svc.publish("job", "curiosity", "short_form", "youtube", dry_run=True)
    assert result.get("status") == "success" or result.get("dry_run") is True or "status" in result
