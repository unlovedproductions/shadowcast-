"""Tests for optional B-roll path resolution."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from broll import (  # noqa: E402
    any_broll_files,
    broll_enabled,
    make_broll_clip,
    resolve_broll_path,
)


def test_resolve_prefers_section_then_pad(tmp_path, monkeypatch):
    monkeypatch.setenv("SHADOWCAST_BROLL", "1")
    bdir = tmp_path / "broll"
    bdir.mkdir()
    (bdir / "pad.mp4").write_bytes(b"fake")
    (bdir / "pros.mp4").write_bytes(b"fake")
    monkeypatch.setattr("broll.broll_dir", lambda: bdir)
    assert resolve_broll_path("pros").endswith("pros.mp4")
    assert resolve_broll_path("unknown").endswith("pad.mp4")


def test_broll_disabled_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SHADOWCAST_BROLL", "0")
    bdir = tmp_path / "broll"
    bdir.mkdir()
    (bdir / "pad.mp4").write_bytes(b"x")
    monkeypatch.setattr("broll.broll_dir", lambda: bdir)
    assert broll_enabled() is False
    assert make_broll_clip("pad") is None


def test_any_broll_false_without_media(tmp_path, monkeypatch):
    bdir = tmp_path / "broll"
    bdir.mkdir()
    (bdir / "ATTRIBUTION.md").write_text("x", encoding="utf-8")
    monkeypatch.setattr("broll.broll_dir", lambda: bdir)
    monkeypatch.delenv("SHADOWCAST_BROLL", raising=False)
    assert any_broll_files() is False
    assert broll_enabled() is False
