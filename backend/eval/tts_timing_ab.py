#!/usr/bin/env python3
"""Lightweight 5-clip A/B harness: LLM-slot trim vs TTS-first duration.

Compares timing generation only (no MoviePy video render suite):

  A = audio_driven=False  — legacy: force speech into LLM duration (can cut words)
  B = audio_driven=True   — TTS-first: duration = speech + inter-segment pause

Default mode uses a deterministic mock TTS (word-rate silence WAV). CI-safe.
Optional ``--live`` uses a real TTS provider when installed.

Run from repo root::

    PYTHONPATH=backend python -m eval.tts_timing_ab
    PYTHONPATH=backend python -m eval.tts_timing_ab --out backend/eval/artifacts/tts_timing_ab.json
    PYTHONPATH=backend python -m eval.tts_timing_ab --fixtures path/to/scripts.json --live --provider gtts

Fixtures JSON: either a list of short_form scripts, or ``{\"clips\": [...]}``.
Each script needs ``segments`` with ``text`` + ``duration`` (LLM slot).
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import tempfile
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from tts_generator import (  # noqa: E402
    _inter_segment_pause,
    generate_voiceover_for_segments,
)

# Words-per-second for mock TTS — slightly slow so tight LLM slots trim under A.
_MOCK_WORDS_PER_SEC = 2.4
_TRIM_EPS = 0.04

# Five synthetic honest_review short_form clips (tight LLM slots → A trims).
DEFAULT_CLIPS: list[dict[str, Any]] = [
    {
        "clip_id": "hr_budget_anc",
        "hook_type": "curiosity",
        "content_style": "honest_review",
        "format": "short_form",
        "title_suggestion": "Budget ANC that actually works?",
        "segments": [
            {"segment_id": 1, "text": "These forty dollar buds claim studio ANC.", "duration": 1.1},
            {"segment_id": 2, "text": "Commute noise drops hard on the train.", "duration": 1.0},
            {"segment_id": 3, "text": "Bass is muddy above seventy percent volume.", "duration": 1.1},
            {"segment_id": 4, "text": "Worth it if you hate subway roar.", "duration": 0.9},
        ],
    },
    {
        "clip_id": "hr_battery_claim",
        "hook_type": "data_bomb",
        "content_style": "honest_review",
        "format": "short_form",
        "title_suggestion": "Fifty hour battery — real or marketing?",
        "segments": [
            {"segment_id": 1, "text": "Fifty hours sounds impossible for this price.", "duration": 1.15},
            {"segment_id": 2, "text": "I got forty two with ANC on all day.", "duration": 1.05},
            {"segment_id": 3, "text": "Case charge is slow but it still beats AirPods.", "duration": 1.2},
            {"segment_id": 4, "text": "Buy for stamina, not for premium fit.", "duration": 1.0},
        ],
    },
    {
        "clip_id": "hr_fit_issues",
        "hook_type": "problem_agitation",
        "content_style": "honest_review",
        "format": "short_form",
        "title_suggestion": "Great sound — if they stay in your ears",
        "segments": [
            {"segment_id": 1, "text": "Small ears will fight these tips all morning.", "duration": 1.1},
            {"segment_id": 2, "text": "Foam tips fixed the seal for my runs.", "duration": 1.0},
            {"segment_id": 3, "text": "Without that seal the ANC falls apart.", "duration": 0.95},
            {"segment_id": 4, "text": "Check tip sizes before you return them.", "duration": 1.0},
        ],
    },
    {
        "clip_id": "hr_call_quality",
        "hook_type": "myth_buster",
        "content_style": "honest_review",
        "format": "short_form",
        "title_suggestion": "Call quality myth vs desk reality",
        "segments": [
            {"segment_id": 1, "text": "Reviews say calls are crystal — outdoors they are not.", "duration": 1.25},
            {"segment_id": 2, "text": "Wind shreds the mics on a windy block.", "duration": 1.0},
            {"segment_id": 3, "text": "Quiet rooms sound fine for standups.", "duration": 0.95},
            {"segment_id": 4, "text": "Desk warrior yes, street calls no.", "duration": 0.9},
        ],
    },
    {
        "clip_id": "hr_verdict_cta",
        "hook_type": "listicle",
        "content_style": "honest_review",
        "format": "short_form",
        "title_suggestion": "Honest verdict in under thirty seconds",
        "segments": [
            {"segment_id": 1, "text": "Who this is for: commuters on a budget.", "duration": 1.05},
            {"segment_id": 2, "text": "Who should skip: anyone needing pro calls outdoors.", "duration": 1.2},
            {"segment_id": 3, "text": "Score: eight out of ten for the price.", "duration": 1.0},
            {"segment_id": 4, "text": "Link below for the current deal.", "duration": 0.85},
        ],
    },
]


def mock_tts_duration_seconds(text: str, words_per_sec: float = _MOCK_WORDS_PER_SEC) -> float:
    words = max(1, len((text or "").split()))
    return max(0.35, words / max(0.5, float(words_per_sec)))


def _write_silence_wav(path: str, duration_s: float, rate: int = 24000) -> None:
    n = max(1, int(duration_s * rate))
    frames = (np.zeros(n, dtype=np.int16)).tobytes()
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(frames)


def make_mock_generate(
    words_per_sec: float = _MOCK_WORDS_PER_SEC,
) -> Callable[..., str]:
    def fake_generate(text, output_path, provider="auto", voice=None):
        _write_silence_wav(output_path, mock_tts_duration_seconds(text, words_per_sec))
        return output_path

    return fake_generate


def load_clips(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return copy.deepcopy(DEFAULT_CLIPS)
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, list):
        clips = raw
    elif isinstance(raw, dict) and "clips" in raw:
        clips = raw["clips"]
    else:
        clips = [raw]
    out: list[dict[str, Any]] = []
    for i, clip in enumerate(clips):
        if not isinstance(clip, dict):
            raise ValueError(f"clip {i} must be an object")
        c = copy.deepcopy(clip)
        c.setdefault("clip_id", c.get("title_suggestion") or f"clip_{i}")
        c.setdefault("format", "short_form")
        c.setdefault("content_style", "honest_review")
        if "segments" not in c:
            raise ValueError(f"clip {c['clip_id']} missing segments")
        out.append(c)
    return out


def _segment_compare(
    llm_duration: float | None,
    row_a: dict[str, Any],
    row_b: dict[str, Any],
) -> dict[str, Any]:
    tts_a = float(row_a.get("tts_duration") or 0.0)
    tts_b = float(row_b.get("tts_duration") or 0.0)
    dur_a = float(row_a.get("duration") or 0.0)
    dur_b = float(row_b.get("duration") or 0.0)
    trimmed = tts_a + _TRIM_EPS < tts_b
    pad_b = max(0.0, dur_b - tts_b)
    return {
        "index": row_b.get("index", row_a.get("index")),
        "text": row_b.get("text") or row_a.get("text") or "",
        "llm_duration": round(llm_duration, 3) if llm_duration is not None else None,
        "tts_duration_a": round(tts_a, 3),
        "tts_duration_b": round(tts_b, 3),
        "final_duration_a": round(dur_a, 3),
        "final_duration_b": round(dur_b, 3),
        "speech_trimmed_a": trimmed,
        "length_delta_b_minus_a": round(dur_b - dur_a, 3),
        "pad_seconds_b": round(pad_b, 3),
        # Proxy: trim severity (seconds of speech lost under A).
        "trim_seconds_a": round(max(0.0, tts_b - tts_a), 3),
    }


def compare_clip(
    script: dict[str, Any],
    *,
    work_dir: Path,
    live: bool = False,
    provider: str = "gtts",
    voice: str | None = None,
    mock_generate: Callable[..., str] | None = None,
) -> dict[str, Any]:
    """Run A (legacy trim) vs B (audio_driven) for one short_form script."""
    segments_src = script.get("segments") or []
    clip_id = str(script.get("clip_id") or script.get("title_suggestion") or "clip")
    work_dir.mkdir(parents=True, exist_ok=True)

    segs_a = copy.deepcopy(segments_src)
    segs_b = copy.deepcopy(segments_src)
    out_a = str(work_dir / f"{clip_id}_A.mp3")
    out_b = str(work_dir / f"{clip_id}_B.mp3")

    gen_kwargs = dict(
        provider=provider if live else "gtts",
        voice=voice,
        write_timing=False,
        transition_gaps=[0.0] * len(segments_src),
        chrome_gaps=[0.0] * len(segments_src),
        leading_chrome=0.0,
    )

    def _run():
        _path_a, timing_a = generate_voiceover_for_segments(
            segs_a, out_a, audio_driven=False, apply_durations=False, **gen_kwargs
        )
        _path_b, timing_b = generate_voiceover_for_segments(
            segs_b, out_b, audio_driven=True, apply_durations=False, **gen_kwargs
        )
        return timing_a, timing_b

    if live:
        timing_a, timing_b = _run()
    else:
        fake = mock_generate or make_mock_generate()
        with patch("tts_generator.generate_segment_audio", side_effect=fake):
            timing_a, timing_b = _run()

    by_a = {int(r["index"]): r for r in timing_a}
    by_b = {int(r["index"]): r for r in timing_b}
    indices = sorted(set(by_a) | set(by_b))
    segments_out: list[dict[str, Any]] = []
    for idx in indices:
        llm = None
        if idx < len(segments_src):
            try:
                llm = float(segments_src[idx].get("duration") or 0) or None
            except (TypeError, ValueError):
                llm = None
        if idx not in by_a or idx not in by_b:
            continue
        segments_out.append(_segment_compare(llm, by_a[idx], by_b[idx]))

    total_a = sum(float(r.get("duration") or 0) for r in timing_a)
    total_b = sum(float(r.get("duration") or 0) for r in timing_b)
    trimmed_n = sum(1 for s in segments_out if s["speech_trimmed_a"])
    return {
        "clip_id": clip_id,
        "content_style": script.get("content_style"),
        "format": script.get("format"),
        "mode": "live" if live else "mock",
        "provider": provider if live else "mock_wav",
        "pause_seconds": round(_inter_segment_pause(), 3),
        "segments": segments_out,
        "totals": {
            "duration_a": round(total_a, 3),
            "duration_b": round(total_b, 3),
            "length_delta_b_minus_a": round(total_b - total_a, 3),
            "segments_trimmed_a": trimmed_n,
            "segments_total": len(segments_out),
            "trim_rate_a": round(trimmed_n / len(segments_out), 3) if segments_out else 0.0,
        },
    }


def run_ab(
    clips: list[dict[str, Any]] | None = None,
    *,
    live: bool = False,
    provider: str = "gtts",
    voice: str | None = None,
    work_dir: Path | None = None,
    mock_generate: Callable[..., str] | None = None,
) -> dict[str, Any]:
    clips = clips if clips is not None else copy.deepcopy(DEFAULT_CLIPS)
    cleanup = work_dir is None
    root = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="tts_ab_"))
    root.mkdir(parents=True, exist_ok=True)

    results = [
        compare_clip(
            clip,
            work_dir=root / str(clip.get("clip_id") or f"clip_{i}"),
            live=live,
            provider=provider,
            voice=voice,
            mock_generate=mock_generate,
        )
        for i, clip in enumerate(clips)
    ]

    clipped = sum(1 for r in results if r["totals"]["segments_trimmed_a"] > 0)
    total_trim_segs = sum(r["totals"]["segments_trimmed_a"] for r in results)
    total_delta = sum(r["totals"]["length_delta_b_minus_a"] for r in results)
    clips_without_trim = len(results) - clipped
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment": "tts_timing_ab",
        "description": "A=LLM-slot trim (audio_driven=False) vs B=TTS-first (audio_driven=True)",
        "mode": "live" if live else "mock",
        "provider": provider if live else "mock_wav",
        "pause_seconds": round(_inter_segment_pause(), 3),
        "clip_count": len(results),
        "summary": {
            "clips_with_trim_under_a": clipped,
            "clips_without_trim_under_a": clips_without_trim,
            "segments_trimmed_under_a": total_trim_segs,
            "total_length_delta_b_minus_a": round(total_delta, 3),
            "note": (
                "speech_trimmed_a is a cut-off proxy (A tts_duration < B). "
                "Naturalness: prefer B when trim_rate_a > 0; length_delta is expected pad."
            ),
        },
        "clips": results,
    }
    if cleanup:
        report["work_dir_ephemeral"] = str(root)
    else:
        report["work_dir"] = str(root)
    return report


def default_report_path() -> Path:
    return Path(__file__).resolve().parent / "artifacts" / "tts_timing_ab.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TTS timing A/B harness (trim vs pad)")
    parser.add_argument(
        "--fixtures",
        type=str,
        default=None,
        help="JSON file of scripts / {clips:[...]}; default = 5 synthetic honest_review shorts",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(default_report_path()),
        help="JSON report path (default: backend/eval/artifacts/tts_timing_ab.json)",
    )
    parser.add_argument(
        "--work-dir",
        type=str,
        default=None,
        help="Keep generated VO files under this directory",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use real TTS (requires network/provider). Default is mock WAV.",
    )
    parser.add_argument("--provider", type=str, default="gtts", help="TTS provider when --live")
    parser.add_argument("--voice", type=str, default=None)
    parser.add_argument(
        "--pause",
        type=float,
        default=None,
        help="Override SHADOWCAST_TTS_INTER_SEGMENT_PAUSE for this run",
    )
    parser.add_argument(
        "--require-trimmed-under-a",
        type=int,
        default=None,
        help=(
            "Optional CI guard: fail (exit 2) if summary.segments_trimmed_under_a "
            "is below this value"
        ),
    )
    args = parser.parse_args(argv)

    if args.require_trimmed_under_a is not None and args.require_trimmed_under_a < 0:
        parser.error("--require-trimmed-under-a must be >= 0")

    if args.pause is not None:
        os.environ["SHADOWCAST_TTS_INTER_SEGMENT_PAUSE"] = str(args.pause)

    clips = load_clips(args.fixtures)
    report = run_ab(
        clips,
        live=args.live,
        provider=args.provider,
        voice=args.voice,
        work_dir=Path(args.work_dir) if args.work_dir else None,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    s = report["summary"]
    print(
        f"Wrote {out} · clips={report['clip_count']} · "
        f"trimmed_segs_A={s['segments_trimmed_under_a']} · "
        f"ΔB−A={s['total_length_delta_b_minus_a']}s"
    )
    if args.require_trimmed_under_a is not None:
        observed = int(s["segments_trimmed_under_a"])
        if observed < args.require_trimmed_under_a:
            print(
                "FAIL require-trimmed-under-a: "
                f"required={args.require_trimmed_under_a} observed={observed}",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
