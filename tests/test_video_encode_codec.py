"""Encode codec resolution (NVENC vs libx264)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import video_renderer as vr  # noqa: E402
from moviepy import config as moviepy_config  # noqa: E402
from moviepy.video.io import ffmpeg_writer as moviepy_ffmpeg_writer  # noqa: E402


def test_resolve_write_videofile_kwargs_software(monkeypatch):
    monkeypatch.setenv("SHADOWCAST_FFMPEG_CODEC", "libx264")
    monkeypatch.setattr(vr, "_nvenc_available", True)
    kw = vr.resolve_write_videofile_kwargs("slow")
    assert kw["codec"] == "libx264"
    assert kw["preset"] == "slow"
    params = kw["ffmpeg_params"]
    assert params[params.index("-b:v") + 1] == "8M"
    assert params[params.index("-minrate") + 1] == "8M"
    assert "-pix_fmt" in params
    assert params[params.index("-profile:v") + 1] == "high"
    assert "bt709" in params


def test_resolve_write_videofile_kwargs_nvenc_forced(monkeypatch):
    monkeypatch.setenv("SHADOWCAST_FFMPEG_CODEC", "h264_nvenc")
    monkeypatch.setattr(vr, "_nvenc_available", False)
    monkeypatch.setattr(vr, "ensure_moviepy_nvenc_ffmpeg", lambda: False)
    kw = vr.resolve_write_videofile_kwargs("medium")
    assert kw["codec"] == "h264_nvenc"
    assert kw["preset"] == "p4"
    params = kw["ffmpeg_params"]
    assert params[params.index("-rc") + 1] == "cbr"
    assert params[params.index("-b:v") + 1] == "8M"
    assert params[params.index("-profile:v") + 1] == "high"
    assert "bt709" in params


def test_resolve_write_videofile_kwargs_auto_uses_nvenc(monkeypatch):
    monkeypatch.setenv("SHADOWCAST_FFMPEG_CODEC", "auto")
    monkeypatch.setattr(vr, "_nvenc_available", True)
    kw = vr.resolve_write_videofile_kwargs("veryfast")
    assert kw["codec"] == "h264_nvenc"
    assert kw["preset"] == "p2"


def test_auto_rebinds_to_system_ffmpeg_when_moviepy_lacks_nvenc(monkeypatch):
    monkeypatch.setenv("SHADOWCAST_FFMPEG_CODEC", "auto")
    monkeypatch.setattr(vr, "_nvenc_available", None)
    monkeypatch.setattr(vr, "moviepy_ffmpeg_binary", lambda: "/bundled/ffmpeg")
    monkeypatch.setattr(vr, "system_ffmpeg_binary", lambda: "/usr/bin/ffmpeg")

    def lists(binary: str) -> bool:
        return binary == "/usr/bin/ffmpeg"

    bound: list[str] = []
    monkeypatch.setattr(vr, "ffmpeg_lists_nvenc", lists)
    monkeypatch.setattr(vr, "bind_moviepy_ffmpeg_binary", lambda b: bound.append(b))

    kw = vr.resolve_write_videofile_kwargs("medium")
    assert kw["codec"] == "h264_nvenc"
    assert bound == ["/usr/bin/ffmpeg"]
    assert vr._nvenc_available is True


def test_auto_falls_back_to_libx264_when_no_nvenc(monkeypatch):
    monkeypatch.setenv("SHADOWCAST_FFMPEG_CODEC", "auto")
    monkeypatch.setattr(vr, "_nvenc_available", None)
    monkeypatch.setattr(vr, "moviepy_ffmpeg_binary", lambda: "/bundled/ffmpeg")
    monkeypatch.setattr(vr, "system_ffmpeg_binary", lambda: "/usr/bin/ffmpeg")
    monkeypatch.setattr(vr, "ffmpeg_lists_nvenc", lambda _binary: False)

    kw = vr.resolve_write_videofile_kwargs("medium")
    assert kw["codec"] == "libx264"
    assert kw["preset"] == "medium"
    assert vr._nvenc_available is False


def test_bind_moviepy_ffmpeg_binary_updates_config_and_writer():
    old_config = moviepy_config.FFMPEG_BINARY
    old_writer = moviepy_ffmpeg_writer.FFMPEG_BINARY
    old_env = os.environ.get("FFMPEG_BINARY")
    target = "/usr/bin/ffmpeg-test-bind"
    try:
        vr.bind_moviepy_ffmpeg_binary(target)
        assert moviepy_config.FFMPEG_BINARY == target
        assert moviepy_ffmpeg_writer.FFMPEG_BINARY == target
        assert os.environ["FFMPEG_BINARY"] == target
    finally:
        moviepy_config.FFMPEG_BINARY = old_config
        moviepy_ffmpeg_writer.FFMPEG_BINARY = old_writer
        if old_env is None:
            os.environ.pop("FFMPEG_BINARY", None)
        else:
            os.environ["FFMPEG_BINARY"] = old_env
