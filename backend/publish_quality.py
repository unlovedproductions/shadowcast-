"""Pre-publish quality checklist for ShadowCast job assets."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tts_generator import get_best_provider as get_best_tts
from video_claims import FORMAT_CLAIMS, LONG_FORM, SHORT_FORM
from visual_quality import audit_thumbnail_contrast


def _ffprobe_duration(path: Path) -> float | None:
    import json
    import shutil
    import subprocess

    if not path.exists() or not shutil.which("ffprobe"):
        return None
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        if proc.returncode != 0:
            return None
        data = json.loads(proc.stdout or "{}")
        return float(data.get("format", {}).get("duration"))
    except Exception:
        return None


def evaluate_publish_quality(
    *,
    video_path: str | Path,
    thumbnail_path: str | Path | None = None,
    video_format: str = SHORT_FORM,
    use_tts_expected: bool = True,
) -> dict[str, Any]:
    """
    Return checklist items with status PASS|WARN|FAIL.

    Does not upload; intended for dry-run gate before live publish.
    """
    path = Path(video_path)
    fmt = SHORT_FORM if video_format == SHORT_FORM else LONG_FORM
    claim = FORMAT_CLAIMS[fmt]
    checks: list[dict[str, str]] = []

    if not path.exists():
        checks.append(
            {
                "id": "video_exists",
                "status": "FAIL",
                "detail": f"Video missing: {path}",
            }
        )
    else:
        checks.append(
            {
                "id": "video_exists",
                "status": "PASS",
                "detail": path.name,
            }
        )

    duration = _ffprobe_duration(path) if path.exists() else None
    if duration is None:
        checks.append(
            {
                "id": "duration_window",
                "status": "WARN",
                "detail": "Could not probe duration (ffprobe unavailable or failed).",
            }
        )
    elif claim.min_duration_seconds <= duration <= claim.max_duration_seconds:
        checks.append(
            {
                "id": "duration_window",
                "status": "PASS",
                "detail": f"{duration:.1f}s within {claim.min_duration_seconds}-{claim.max_duration_seconds}s",
            }
        )
    else:
        checks.append(
            {
                "id": "duration_window",
                "status": "WARN",
                "detail": f"{duration:.1f}s outside {claim.min_duration_seconds}-{claim.max_duration_seconds}s claim window",
            }
        )

    best = get_best_tts()
    quality = best in ("kokoro", "openai", "piper")
    allow_gtts = os.getenv("ALLOW_GTTS_PUBLISH", "").strip() in ("1", "true", "True")
    if quality:
        checks.append(
            {
                "id": "tts_quality",
                "status": "PASS",
                "detail": f"best={best}",
            }
        )
    elif allow_gtts:
        checks.append(
            {
                "id": "tts_quality",
                "status": "WARN",
                "detail": f"best={best}; ALLOW_GTTS_PUBLISH=1",
            }
        )
    else:
        checks.append(
            {
                "id": "tts_quality",
                "status": "FAIL",
                "detail": f"best={best}; install Kokoro/Piper/OpenAI TTS or set ALLOW_GTTS_PUBLISH=1",
            }
        )

    srt = path.with_suffix(".srt")
    sidecars = list(path.parent.glob("*_voiceover_timing.json")) + list(
        path.parent.glob("*_timing.json")
    )
    if srt.exists() or sidecars:
        checks.append(
            {
                "id": "captions_sidecar",
                "status": "PASS",
                "detail": srt.name if srt.exists() else "timing sidecar present",
            }
        )
    elif use_tts_expected:
        checks.append(
            {
                "id": "captions_sidecar",
                "status": "WARN",
                "detail": "No timing/SRT sidecar found beside video",
            }
        )
    else:
        checks.append(
            {
                "id": "captions_sidecar",
                "status": "WARN",
                "detail": "TTS not expected; caption sidecar optional",
            }
        )

    if thumbnail_path:
        thumb = Path(thumbnail_path)
        if not thumb.exists():
            checks.append(
                {
                    "id": "thumbnail_contrast",
                    "status": "WARN",
                    "detail": f"Thumbnail missing: {thumb}",
                }
            )
        else:
            severity, expected, actual, detail = audit_thumbnail_contrast(thumb)
            checks.append(
                {
                    "id": "thumbnail_contrast",
                    "status": severity,
                    "detail": f"{detail} ({actual}, expect {expected})",
                }
            )
    else:
        checks.append(
            {
                "id": "thumbnail_contrast",
                "status": "WARN",
                "detail": "No thumbnail path provided",
            }
        )

    statuses = {c["status"] for c in checks}
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "WARN" in statuses:
        overall = "WARN"
    else:
        overall = "PASS"

    return {
        "overall": overall,
        "checks": checks,
        "video_format": fmt,
        "ready_for_live_publish": overall != "FAIL",
    }
