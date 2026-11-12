"""Optional stock B-roll pads for long-form chapter transitions.

Drop MP4/MOV clips under ``backend/assets/broll/``:

- ``pad.mp4`` — generic chapter pad (used when section-specific missing)
- ``pros.mp4``, ``cons.mp4``, ``verdict.mp4``, ``comparison.mp4`` — section pads

Enable explicitly with ``SHADOWCAST_BROLL=1``, or auto-use when any clip file exists
unless ``SHADOWCAST_BROLL=0``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_BROLL_EXTS = (".mp4", ".mov", ".webm", ".mkv")


def broll_dir() -> Path:
    return Path(__file__).resolve().parent / "assets" / "broll"


def broll_enabled() -> bool:
    raw = (os.getenv("SHADOWCAST_BROLL") or "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return any_broll_files()


def any_broll_files() -> bool:
    root = broll_dir()
    if not root.is_dir():
        return False
    for path in root.iterdir():
        if path.is_file() and path.suffix.lower() in _BROLL_EXTS:
            return True
    return False


def resolve_broll_path(section_type: str | None = None) -> str | None:
    """Return best matching clip path for a chapter section, or None."""
    root = broll_dir()
    if not root.is_dir():
        return None
    keys: list[str] = []
    if section_type:
        keys.append(str(section_type).strip().lower())
    keys.extend(["pad", "default"])
    for key in keys:
        for ext in _BROLL_EXTS:
            candidate = root / f"{key}{ext}"
            if candidate.is_file():
                return str(candidate)
    for path in sorted(root.iterdir()):
        if path.is_file() and path.suffix.lower() in _BROLL_EXTS:
            return str(path)
    return None


def make_broll_clip(
    section_type: str | None = None,
    *,
    duration: float = 2.0,
    width: int = 1920,
    height: int = 1080,
) -> Any | None:
    """
    Build a MoviePy clip from a stock B-roll file, sized for long-form.

    Returns None when disabled, missing files, or load failure (fail soft).
    """
    if not broll_enabled():
        return None
    path = resolve_broll_path(section_type)
    if not path:
        return None
    try:
        from moviepy import (
            ColorClip,
            CompositeVideoClip,
            VideoFileClip,
            concatenate_videoclips,
            vfx,
        )
    except Exception as exc:
        print(f"Warning: B-roll unavailable (moviepy import): {exc}")
        return None
    try:
        src = VideoFileClip(path)
        try:
            src = src.without_audio()
        except Exception:
            pass
        target = max(0.5, float(duration))
        src_dur = float(src.duration or 0)
        if src_dur <= 0:
            src.close()
            return None
        if src_dur < target:
            reps = int(target / src_dur) + 1
            looped = concatenate_videoclips([src] * reps, method="compose")
            src.close()
            src = looped
        clip = src.subclipped(0, min(target, float(src.duration)))
        # Cover-fit: scale by height, center-crop or letterbox to width.
        fitted = clip.resized(height=height)
        if fitted.w >= width:
            x1 = max(0, int((fitted.w - width) / 2))
            fitted = fitted.cropped(x1=x1, y1=0, width=width, height=height)
        else:
            bg = ColorClip(size=(width, height), color=(10, 10, 12), duration=fitted.duration)
            fitted = CompositeVideoClip(
                [bg, fitted.with_position("center")],
                size=(width, height),
            )
        fitted = fitted.with_effects([vfx.FadeIn(0.25), vfx.FadeOut(0.25)])
        return fitted
    except Exception as exc:
        print(f"Warning: B-roll load failed ({path}): {exc}")
        return None
