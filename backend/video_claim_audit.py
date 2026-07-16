"""Audit generated videos against code-level claims."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from content_styles import normalize_content_style
from video_claims import (
    FORMAT_CLAIMS,
    LONG_FORM,
    SHORT_FORM,
    expected_timeline_duration,
    missing_optional_layouts,
    missing_required_layouts,
    sum_segment_durations,
    unsupported_animation_tokens,
    unsupported_transition_tokens,
)


FAIL = "FAIL"
WARN = "WARN"


@dataclass
class Finding:
    job: str
    path: str
    check: str
    severity: str
    expected: str
    actual: str
    detail: str


@dataclass
class ScriptBundle:
    path: Path
    scripts: dict[str, dict[str, Any]]
    content_style: str
    product_info: dict[str, Any]


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_frame_rate(rate: str | None) -> float | None:
    token = str(rate or "").strip()
    if not token:
        return None
    if "/" in token:
        num_s, den_s = token.split("/", 1)
        num = _coerce_float(num_s)
        den = _coerce_float(den_s)
        if num is None or den in (None, 0):
            return None
        return num / den
    return _coerce_float(token)


def _key_from_script_path(path: Path) -> str | None:
    stem = path.stem
    if not stem.endswith("_scripts"):
        return None
    return stem[: -len("_scripts")]


def _key_and_format_from_video_path(path: Path) -> tuple[str | None, str | None]:
    stem = path.stem
    suffix_map = (
        ("_short", SHORT_FORM),
        ("_long", LONG_FORM),
        ("_short_form", SHORT_FORM),
        ("_long_form", LONG_FORM),
    )
    for suffix, fmt in suffix_map:
        if stem.endswith(suffix):
            return stem[: -len(suffix)], fmt
    return None, None


def _load_script_bundle(path: Path) -> ScriptBundle | None:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    format_map: dict[str, dict[str, Any]] = {}
    scripts_node = payload.get("scripts")
    if isinstance(scripts_node, dict):
        for fmt in (SHORT_FORM, LONG_FORM):
            script = scripts_node.get(fmt)
            if isinstance(script, dict):
                format_map[fmt] = script
    else:
        for fmt in (SHORT_FORM, LONG_FORM):
            script = payload.get(fmt)
            if isinstance(script, dict):
                format_map[fmt] = script
        direct_fmt = payload.get("format")
        if isinstance(direct_fmt, str) and direct_fmt in (SHORT_FORM, LONG_FORM) and direct_fmt not in format_map:
            format_map[direct_fmt] = payload

    if not format_map:
        return None

    style = normalize_content_style(str(payload.get("content_style", "")).strip())
    if not style:
        style = normalize_content_style("")
    product_info = payload.get("product_info")
    if not isinstance(product_info, dict):
        product_info = {}
    return ScriptBundle(path=path, scripts=format_map, content_style=style, product_info=product_info)


def _discover_script_bundles(output_dir: Path) -> tuple[dict[tuple[Path, str], ScriptBundle], dict[str, list[ScriptBundle]]]:
    by_directory_key: dict[tuple[Path, str], ScriptBundle] = {}
    by_key: dict[str, list[ScriptBundle]] = {}
    for script_path in sorted(output_dir.rglob("*_scripts.json")):
        key = _key_from_script_path(script_path)
        if not key:
            continue
        bundle = _load_script_bundle(script_path)
        if bundle is None:
            continue
        dir_key = (script_path.parent.resolve(), key)
        by_directory_key[dir_key] = bundle
        by_key.setdefault(key, []).append(bundle)
    return by_directory_key, by_key


def _discover_videos(output_dir: Path) -> list[Path]:
    videos: list[Path] = []
    for path in sorted(output_dir.rglob("*.mp4")):
        if path.name.endswith("_video_only.mp4"):
            continue
        videos.append(path)
    return videos


def _probe_video(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    command = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None, "ffprobe is not installed or not on PATH"
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "ffprobe failed"
        return None, message
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, "ffprobe returned invalid JSON"

    streams = payload.get("streams", [])
    video_stream = None
    if isinstance(streams, list):
        for stream in streams:
            if isinstance(stream, dict) and stream.get("codec_type") == "video":
                video_stream = stream
                break
    if video_stream is None:
        return None, "ffprobe did not return a video stream"

    fmt = payload.get("format")
    fmt_duration = _coerce_float(fmt.get("duration")) if isinstance(fmt, dict) else None
    stream_duration = _coerce_float(video_stream.get("duration"))
    duration = fmt_duration if fmt_duration is not None else stream_duration
    return {
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": _parse_frame_rate(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")),
        "duration": duration,
    }, None


def audit_output(output_dir: Path) -> dict[str, Any]:
    findings: list[Finding] = []
    by_directory_key, by_key = _discover_script_bundles(output_dir)
    videos = _discover_videos(output_dir)

    for video_path in videos:
        rel_path = video_path.relative_to(output_dir)
        job = rel_path.parts[0] if rel_path.parts else ""

        def push(check: str, severity: str, expected: str, actual: str, detail: str) -> None:
            findings.append(
                Finding(
                    job=job,
                    path=str(rel_path),
                    check=check,
                    severity=severity,
                    expected=expected,
                    actual=actual,
                    detail=detail,
                )
            )

        file_size = video_path.stat().st_size if video_path.exists() else 0
        if file_size <= 0:
            push(
                check="file_integrity",
                severity=FAIL,
                expected="non-empty MP4 file",
                actual=f"size={file_size}",
                detail="Artifact cache accepted an empty file.",
            )
            continue

        key, fmt = _key_and_format_from_video_path(video_path)
        if not key or fmt not in (SHORT_FORM, LONG_FORM):
            push(
                check="filename_format",
                severity=FAIL,
                expected="*_short.mp4 or *_long.mp4",
                actual=video_path.name,
                detail="Cannot infer format from filename.",
            )
            continue

        bundle = by_directory_key.get((video_path.parent.resolve(), key))
        if bundle is None:
            push(
                check="script_pairing",
                severity=FAIL,
                expected=f"{key}_scripts.json with {fmt} content",
                actual="missing script bundle",
                detail="Video has no paired script JSON in the same directory.",
            )
            continue

        script = bundle.scripts.get(fmt)
        if not isinstance(script, dict):
            push(
                check="script_format_key",
                severity=FAIL,
                expected=f"{fmt} script in {bundle.path.name}",
                actual="format key missing",
                detail="Video exists but paired script payload lacks this format key.",
            )
            continue

        probe, probe_error = _probe_video(video_path)
        if probe_error:
            push(
                check="file_integrity",
                severity=FAIL,
                expected="ffprobe success",
                actual=probe_error,
                detail="Cannot validate dimensions/fps/duration.",
            )
            continue

        claim = FORMAT_CLAIMS[fmt]
        width = int(probe.get("width") or 0)
        height = int(probe.get("height") or 0)
        fps = _coerce_float(probe.get("fps"))
        duration = _coerce_float(probe.get("duration"))

        if (width, height) != (claim.width, claim.height):
            push(
                check="resolution",
                severity=FAIL,
                expected=f"{claim.width}x{claim.height}",
                actual=f"{width}x{height}",
                detail="Rendered resolution does not match renderer contract.",
            )

        if fps is not None and abs(fps - claim.fps) > 0.25:
            push(
                check="fps",
                severity=WARN,
                expected=f"{claim.fps}",
                actual=f"{fps:.3f}",
                detail="Frame rate differs from renderer target.",
            )

        if duration is not None and not (claim.min_duration_seconds <= duration <= claim.max_duration_seconds):
            push(
                check="duration_window",
                severity=WARN,
                expected=f"{claim.min_duration_seconds}-{claim.max_duration_seconds}s",
                actual=f"{duration:.2f}s",
                detail="Prompt-level duration target was not met.",
            )

        script_total = _coerce_float(script.get("total_duration_seconds"))
        segment_total = sum_segment_durations(script, fmt)
        timeline_expected = expected_timeline_duration(script, fmt)
        if script_total is not None and abs(script_total - segment_total) > 2.0:
            push(
                check="total_vs_segments",
                severity=WARN,
                expected=f"{script_total:.2f}s",
                actual=f"{segment_total:.2f}s",
                detail="Script total_duration_seconds diverges from summed segment durations.",
            )
        if duration is not None and abs(duration - timeline_expected) > 2.5:
            push(
                check="timeline_vs_video",
                severity=WARN,
                expected=f"{timeline_expected:.2f}s",
                actual=f"{duration:.2f}s",
                detail="Rendered duration diverges from segment durations plus renderer chrome.",
            )
        if script_total is not None and duration is not None and abs(duration - script_total) > 5.0:
            push(
                check="total_vs_video",
                severity=WARN,
                expected=f"{script_total:.2f}s",
                actual=f"{duration:.2f}s",
                detail="Declared total duration does not match emitted MP4.",
            )

        style = normalize_content_style(script.get("content_style") or bundle.content_style)
        missing_layouts = missing_required_layouts(style, script, fmt)
        if missing_layouts:
            push(
                check="required_layouts",
                severity=FAIL,
                expected=", ".join(sorted(missing_layouts)),
                actual="missing",
                detail=f"Style {style} is missing required layouts.",
            )

        claimed_optional: set[str] = set()
        if style == "vs_battle":
            comparison_specs = bundle.product_info.get("comparison_specs")
            price_comparison = str(bundle.product_info.get("price_comparison", "")).strip()
            if comparison_specs or price_comparison:
                claimed_optional.add("spec_compare")
        missing_optionals = missing_optional_layouts(style, script, fmt, claimed=claimed_optional or None)
        if missing_optionals:
            push(
                check="claimed_optional_layouts",
                severity=FAIL,
                expected=", ".join(sorted(missing_optionals)),
                actual="missing",
                detail=f"Style {style} claims optional comparison layouts but they are absent.",
            )

        bad_animations = unsupported_animation_tokens(script, fmt)
        if bad_animations:
            push(
                check="unsupported_animations",
                severity=WARN,
                expected="renderer-supported animation tokens",
                actual=", ".join(sorted(bad_animations)),
                detail="Script uses animation tokens without dedicated renderer handlers.",
            )

        bad_transitions = unsupported_transition_tokens(script, fmt)
        if bad_transitions:
            push(
                check="unsupported_transitions",
                severity=WARN,
                expected="renderer-supported transition tokens",
                actual=", ".join(sorted(bad_transitions)),
                detail="Script uses transition tokens without dedicated renderer handlers.",
            )

    fail_count = sum(1 for f in findings if f.severity == FAIL)
    warn_count = sum(1 for f in findings if f.severity == WARN)
    return {
        "output_dir": str(output_dir),
        "videos_checked": len(videos),
        "fail_count": fail_count,
        "warn_count": warn_count,
        "findings": [asdict(f) for f in findings],
    }


def _print_report(result: dict[str, Any]) -> None:
    print(
        f"Videos checked: {result['videos_checked']} | "
        f"FAIL: {result['fail_count']} | WARN: {result['warn_count']}"
    )
    for item in result["findings"]:
        print(
            f"[{item['severity']}] {item['path']} :: {item['check']} "
            f"(expected={item['expected']} actual={item['actual']})"
        )
        if item["detail"]:
            print(f"  -> {item['detail']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit generated videos against ShadowCast claims.")
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent / "output"),
        help="Directory containing job output artifacts.",
    )
    parser.add_argument("--json-out", help="Write full findings JSON to this path.")
    parser.add_argument(
        "--fail-on",
        choices=("fail", "warn"),
        default="fail",
        help="Exit non-zero on fail findings only, or on any warning.",
    )
    parser.add_argument(
        "--require-videos",
        action="store_true",
        help="Exit non-zero if no MP4 files are found.",
    )
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir).expanduser().resolve()
    result = audit_output(output_dir)
    _print_report(result)

    if args.json_out:
        out_path = Path(args.json_out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2))

    if result["videos_checked"] == 0:
        print(f"No MP4 artifacts found under {output_dir}.")
        return 1 if args.require_videos else 0
    if result["fail_count"] > 0:
        return 1
    if args.fail_on == "warn" and result["warn_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
