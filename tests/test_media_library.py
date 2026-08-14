"""Media library inventory / search."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from media_library import media_library_snapshot  # noqa: E402


def test_media_library_lists_expected_slots(tmp_path, monkeypatch):
    music = tmp_path / "music"
    broll = tmp_path / "broll"
    music.mkdir()
    broll.mkdir()
    (music / "chill.wav").write_bytes(b"RIFF")
    (broll / "pad.mp4").write_bytes(b"ftyp")

    monkeypatch.setattr("media_library.music_dir", lambda: music)
    monkeypatch.setattr("media_library.broll_dir", lambda: broll)

    snap = media_library_snapshot()
    assert "chill" in snap["music"]["present"]
    assert "energetic" in snap["music"]["missing"]
    assert "pad" in snap["broll"]["present"]
    assert "pros" in snap["broll"]["missing"]
    assert snap["summary"]["complete"] is False


def test_media_library_search_filters(tmp_path, monkeypatch):
    music = tmp_path / "music"
    broll = tmp_path / "broll"
    music.mkdir()
    broll.mkdir()
    (music / "dramatic.wav").write_bytes(b"x")
    (broll / "verdict.mp4").write_bytes(b"y")

    monkeypatch.setattr("media_library.music_dir", lambda: music)
    monkeypatch.setattr("media_library.broll_dir", lambda: broll)

    snap = media_library_snapshot(query="verdict")
    assert snap["query"] == "verdict"
    assert len(snap["broll"]["items"]) >= 1
    assert all("verdict" in i["id"].lower() or "verdict" in i["tags"] for i in snap["broll"]["items"])
    assert snap["music"]["items"] == []
