"""Encode codec resolution (NVENC vs libx264)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import video_renderer as vr  # noqa: E402


def test_resolve_write_videofile_kwargs_software(monkeypatch):
    monkeypatch.setenv("SHADOWCAST_FFMPEG_CODEC", "libx264")
    monkeypatch.setattr(vr, "_nvenc_available", True)
    kw = vr.resolve_write_videofile_kwargs("slow")
    assert kw["codec"] == "libx264"
    assert kw["preset"] == "slow"
    assert "-pix_fmt" in kw["ffmpeg_params"]


def test_resolve_write_videofile_kwargs_nvenc_forced(monkeypatch):
    monkeypatch.setenv("SHADOWCAST_FFMPEG_CODEC", "h264_nvenc")
    monkeypatch.setattr(vr, "_nvenc_available", False)
    kw = vr.resolve_write_videofile_kwargs("medium")
    assert kw["codec"] == "h264_nvenc"
    assert kw["preset"] == "p4"
    assert "-cq" in kw["ffmpeg_params"]


def test_resolve_write_videofile_kwargs_auto_uses_nvenc(monkeypatch):
    monkeypatch.setenv("SHADOWCAST_FFMPEG_CODEC", "auto")
    monkeypatch.setattr(vr, "_nvenc_available", True)
    kw = vr.resolve_write_videofile_kwargs("veryfast")
    assert kw["codec"] == "h264_nvenc"
    assert kw["preset"] == "p2"
