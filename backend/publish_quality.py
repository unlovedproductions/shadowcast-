"""Pre-publish quality checklist for ShadowCast job assets."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from broll import any_broll_files
from sound_design import music_bed_moods, music_beds_present
from tts_generator import get_best_provider as get_best_tts
from video_claim_audit import audit_output
from video_claims import FORMAT_CLAIMS, LONG_FORM, SHORT_FORM
from visual_quality import audit_product_sharpness, audit_thumbnail_contrast


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


def _claim_audit_check(video_path: Path) -> dict[str, str]:
    """Run directory claim audit and project findings for this video."""
    try:
        report = audit_output(video_path.parent)
    except Exception as exc:
        return {
            "id": "claim_audit",
            "status": "WARN",
            "detail": f"Claim audit skipped: {exc}",
        }

    name = video_path.name
    relevant = [
        f
        for f in (report.get("findings") or [])
        if name in str(f.get("path") or "")
    ]
    fails = [f for f in relevant if f.get("severity") == "FAIL"]
    warns = [f for f in relevant if f.get("severity") == "WARN"]
    if fails:
        first = fails[0]
        return {
            "id": "claim_audit",
            "status": "FAIL",
            "detail": f"{len(fails)} FAIL — {first.get('check')}: {first.get('detail') or first.get('actual')}",
        }
    if warns:
        first = warns[0]
        return {
            "id": "claim_audit",
            "status": "WARN",
            "detail": f"{len(warns)} WARN — {first.get('check')}: {first.get('detail') or first.get('actual')}",
        }
    if report.get("videos_checked", 0) == 0:
        return {
            "id": "claim_audit",
            "status": "WARN",
            "detail": "No videos discovered for claim audit in parent directory",
        }
    # Findings only record FAIL/WARN — an empty match means this video passed silently.
    return {
        "id": "claim_audit",
        "status": "PASS",
        "detail": "No FAIL/WARN claim findings for this video",
    }


def evaluate_publish_quality(
    *,
    video_path: str | Path,
    thumbnail_path: str | Path | None = None,
    video_format: str = SHORT_FORM,
    use_tts_expected: bool = True,
    image_url: str | None = None,
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

    if path.exists():
        checks.append(_claim_audit_check(path))
    else:
        checks.append(
            {
                "id": "claim_audit",
                "status": "FAIL",
                "detail": "Skipped — video missing",
            }
        )

    moods = music_bed_moods()
    allow_synth = os.getenv("ALLOW_SYNTH_MUSIC_PUBLISH", "").strip() in ("1", "true", "True")
    if music_beds_present():
        checks.append(
            {
                "id": "music_bed",
                "status": "PASS",
                "detail": f"beds={','.join(moods)}",
            }
        )
    elif allow_synth:
        checks.append(
            {
                "id": "music_bed",
                "status": "WARN",
                "detail": "No royalty-free beds; synth fallback allowed (ALLOW_SYNTH_MUSIC_PUBLISH=1)",
            }
        )
    else:
        checks.append(
            {
                "id": "music_bed",
                "status": "FAIL",
                "detail": "No assets/music/{mood}.wav beds; run scripts/fetch_operator_media.sh or set ALLOW_SYNTH_MUSIC_PUBLISH=1",
            }
        )

    if any_broll_files():
        checks.append(
            {
                "id": "broll_pack",
                "status": "PASS",
                "detail": "B-roll clips present under assets/broll/",
            }
        )
    else:
        checks.append(
            {
                "id": "broll_pack",
                "status": "WARN",
                "detail": "No B-roll clips; long-form pads will skip (run scripts/fetch_operator_media.sh)",
            }
        )

    image = (image_url or "").strip()
    require_raw = (os.getenv("SHADOWCAST_REQUIRE_PRODUCT_IMAGE") or "1").strip().lower()
    require_image = require_raw not in ("0", "false", "no", "off")
    if image:
        checks.append(
            {
                "id": "product_image",
                "status": "PASS",
                "detail": "image_url present",
            }
        )
        try:
            from product_media import resolve_product_image

            cached = resolve_product_image(image)
            if cached is not None:
                sev, expected, actual, detail = audit_product_sharpness(cached)
                checks.append(
                    {
                        "id": "product_sharpness",
                        "status": sev,
                        "detail": f"{detail} ({actual}, expect {expected})",
                    }
                )
        except Exception as exc:
            checks.append(
                {
                    "id": "product_sharpness",
                    "status": "WARN",
                    "detail": f"Product sharpness check skipped: {exc}",
                }
            )
    elif require_image:
        checks.append(
            {
                "id": "product_image",
                "status": "FAIL",
                "detail": "image_url missing; set a product still or SHADOWCAST_REQUIRE_PRODUCT_IMAGE=0",
            }
        )
    else:
        checks.append(
            {
                "id": "product_image",
                "status": "WARN",
                "detail": "image_url missing — thumbs/product stills will be weaker",
            }
        )

    if thumbnail_path:
        thumb = Path(thumbnail_path)
        # Prefer auto best-contrast pick already done by resolve_job_assets; flag dense overlay text.
        # Packaging truth: long thumb copy often means clickbait mismatch risk.
        # (Detailed package fields are optional — only warn when sidecar JSON sits beside video.)
        pkg_candidates = list(path.parent.glob("*_youtube_package.json")) if path.exists() else []
        if pkg_candidates:
            try:
                pkg = json.loads(pkg_candidates[0].read_text(encoding="utf-8"))
                primary = str((pkg or {}).get("thumbnail_text_primary") or "").strip()
                primary_words = len(primary.split()) if primary else 0
                if primary_words > 6:
                    checks.append(
                        {
                            "id": "thumb_packaging",
                            "status": "WARN",
                            "detail": f"thumbnail_text_primary has {primary_words} words (keep ≤6 for billboard readability)",
                        }
                    )
                elif primary:
                    checks.append(
                        {
                            "id": "thumb_packaging",
                            "status": "PASS",
                            "detail": "thumbnail packaging looks concise; deliver on title promise in first seconds",
                        }
                    )
                else:
                    checks.append(
                        {
                            "id": "thumb_packaging",
                            "status": "WARN",
                            "detail": "youtube package missing thumbnail_text_primary",
                        }
                    )
            except Exception:
                checks.append(
                    {
                        "id": "thumb_packaging",
                        "status": "WARN",
                        "detail": "Could not read youtube package for thumb packaging check",
                    }
                )
        elif thumb.exists():
            checks.append(
                {
                    "id": "thumb_packaging",
                    "status": "WARN",
                    "detail": "Thumbnail file present but no youtube package for packaging check",
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
