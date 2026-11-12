#!/usr/bin/env python3
"""Deterministic short/long render benchmark for before/after measurement."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from video_claim_audit import audit_output  # noqa: E402
from video_renderer import render_long_form_video, render_short_form_video  # noqa: E402


SHORT_FIXTURE = {
    "hook_type": "benchmark",
    "format": "short_form",
    "total_duration_seconds": 12,
    "title_suggestion": "Benchmark Short",
    "segments": [
        {
            "segment_id": 1,
            "duration": 2.0,
            "text": "THIS CHANGES EVERYTHING",
            "text_style": "headline_bold",
            "text_color": "#FFFFFF",
            "bg_color": "#0A0A0F",
            "animation": "fade_in",
            "transition_to_next": "glitch",
            "layout": None,
        },
        {
            "segment_id": 2,
            "duration": 2.0,
            "text": "4.8 STARS",
            "text_style": "stat_number",
            "text_color": "#FFD700",
            "bg_color": "#0A0A0F",
            "animation": "impact_scale",
            "transition_to_next": "flash",
        },
        {
            "segment_id": 3,
            "duration": 2.0,
            "text": "Link in description",
            "text_style": "cta_button",
            "text_color": "#FFFFFF",
            "bg_color": "#0A0A0F",
            "animation": "slide_up",
            "transition_to_next": "fade",
        },
    ],
}

LONG_FIXTURE = {
    "hook_type": "benchmark",
    "format": "long_form",
    "total_duration_seconds": 30,
    "title_suggestion": "Benchmark Long",
    "chapters": [
        {
            "chapter_name": "Hook",
            "segments": [
                {
                    "segment_id": 1,
                    "duration": 2.5,
                    "text": "Let's break this down",
                    "text_style": "headline_bold",
                    "animation": "fade_in",
                    "transition_to_next": "swipe",
                },
                {
                    "segment_id": 2,
                    "duration": 2.5,
                    "text": "Key claim",
                    "text_style": "subtitle",
                    "animation": "fade_in",
                    "transition_to_next": "cut",
                },
            ],
        },
        {
            "chapter_name": "Verdict",
            "segments": [
                {
                    "segment_id": 3,
                    "duration": 2.5,
                    "text": "Final take",
                    "text_style": "verdict",
                    "animation": "fade_in",
                    "transition_to_next": "fade",
                },
            ],
        },
    ],
}


def _ffprobe(path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    raw = subprocess.check_output(cmd, text=True)
    return json.loads(raw)


def _run_one(fmt: str, out_dir: Path, preset: str, audio: bool) -> dict:
    out = out_dir / f"benchmark_{fmt}.mp4"
    t0 = time.perf_counter()
    if fmt == "short_form":
        render_short_form_video(
            SHORT_FIXTURE,
            str(out),
            product_name="Benchmark Product",
            price="$49.99",
            series_name="Worth It?",
            audio_enabled=audio,
            use_tts=False,
            video_preset=preset,
        )
    else:
        render_long_form_video(
            LONG_FIXTURE,
            str(out),
            product_name="Benchmark Product",
            price="$49.99",
            series_name="Worth It?",
            audio_enabled=audio,
            use_tts=False,
            video_preset=preset,
        )
    wall_s = time.perf_counter() - t0
    probe = _ffprobe(out)
    streams = probe.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    return {
        "format": fmt,
        "path": str(out),
        "wall_seconds": round(wall_s, 3),
        "size_bytes": out.stat().st_size,
        "duration": float(probe.get("format", {}).get("duration") or 0),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": video.get("r_frame_rate"),
        "has_audio": audio_stream is not None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=["short_form", "long_form", "both"], default="short_form")
    parser.add_argument("--preset", default=os.getenv("SHADOWCAST_VIDEO_PRESET", "ultrafast"))
    parser.add_argument("--audio", action="store_true")
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else Path(tempfile.mkdtemp(prefix="shadowcast_bench_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    formats = ["short_form", "long_form"] if args.format == "both" else [args.format]
    results = [_run_one(fmt, out_dir, args.preset, args.audio) for fmt in formats]
    audit = audit_output(out_dir)
    payload = {"results": results, "audit_summary": audit.get("summary", audit)}
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
