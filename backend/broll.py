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

import numpy as np

from visual_quality import frame_sharpness_score

_BROLL_EXTS = (".mp4", ".mov", ".webm", ".mkv")
_FALLBACK_KEYS = ("pad", "default")
# Mild grade toward kinetic brand bg so Mixkit pads don't look like another show.
_BRAND_BG = np.array([10.0, 10.0, 15.0], dtype=np.float32)
_GRADE_STRENGTH = 0.12
_SAMPLE_COUNT = 6


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


def _find_clip(root: Path, key: str) -> str | None:
    for ext in _BROLL_EXTS:
        candidate = root / f"{key}{ext}"
        if candidate.is_file():
            return str(candidate)
    return None


def resolve_broll_path(section_type: str | None = None) -> str | None:
    """Return section clip, then pad/default fallback."""
    root = broll_dir()
    if not root.is_dir():
        return None
    key = str(section_type or "").strip().lower()
    if key:
        hit = _find_clip(root, key)
        if hit:
            return hit
    for fallback in _FALLBACK_KEYS:
        if fallback == key:
            continue
        hit = _find_clip(root, fallback)
        if hit:
            return hit
    return None


def best_broll_window_start(
    scores: list[float],
    *,
    src_duration: float,
    target_duration: float,
) -> float:
    """
    Pick start time for a target-length window given evenly spaced sample scores.

    Pure helper for unit tests (no MoviePy).
    """
    if not scores or src_duration <= 0 or target_duration <= 0:
        return 0.0
    n = len(scores)
    if n == 1 or target_duration >= src_duration:
        return 0.0
    # Sample times at midpoints of equal bins across [0, src_duration].
    sample_t = [(i + 0.5) * src_duration / n for i in range(n)]
    max_start = max(0.0, src_duration - target_duration)
    best_start = 0.0
    best_mean = -1.0
    # Evaluate candidate windows starting at each sample that can fit.
    for i, t0 in enumerate(sample_t):
        start = min(max(0.0, t0 - target_duration * 0.35), max_start)
        end = start + target_duration
        covered = [scores[j] for j, tj in enumerate(sample_t) if start <= tj <= end]
        if not covered:
            covered = [scores[i]]
        mean = sum(covered) / len(covered)
        if mean > best_mean:
            best_mean = mean
            best_start = start
    return float(best_start)


def _sample_frame_scores(clip, src_duration: float) -> list[float]:
    scores: list[float] = []
    n = _SAMPLE_COUNT
    for i in range(n):
        t = min(src_duration - 1e-3, (i + 0.5) * src_duration / n)
        t = max(0.0, t)
        try:
            frame = clip.get_frame(t)
            score = frame_sharpness_score(frame)
            scores.append(float(score) if score is not None else 0.0)
        except Exception:
            scores.append(0.0)
    return scores


def _brand_grade_frame(get_frame, t):
    fr = np.asarray(get_frame(t), dtype=np.float32)
    if fr.ndim != 3 or fr.shape[2] < 3:
        return get_frame(t)
    graded = fr[..., :3] * (1.0 - _GRADE_STRENGTH) + _BRAND_BG * _GRADE_STRENGTH
    out = np.clip(graded, 0, 255).astype(np.uint8)
    if fr.shape[2] > 3:
        return np.concatenate([out, fr[..., 3:]], axis=-1)
    return out


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

        window_start = 0.0
        if src_dur > target:
            scores = _sample_frame_scores(src, src_dur)
            window_start = best_broll_window_start(
                scores, src_duration=src_dur, target_duration=target
            )

        if src_dur < target:
            reps = int(target / src_dur) + 1
            looped = concatenate_videoclips([src] * reps, method="compose")
            src.close()
            src = looped
            clip = src.subclipped(0, min(target, float(src.duration)))
        else:
            end = min(src_dur, window_start + target)
            clip = src.subclipped(window_start, end)

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
        try:
            fitted = fitted.transform(_brand_grade_frame)
        except Exception:
            pass
        fitted = fitted.with_effects([vfx.FadeIn(0.25), vfx.FadeOut(0.25)])
        return fitted
    except Exception as exc:
        print(f"Warning: B-roll load failed ({path}): {exc}")
        return None
