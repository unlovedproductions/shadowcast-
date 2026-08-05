"""SRT sidecar generation from shared TTS timing rows."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def timing_rows_to_srt(
    timing_rows: list[dict[str, Any]],
    *,
    intro_offset: float = 0.0,
) -> str:
    """Build SRT text from TTS timing rows (shared clock)."""
    blocks: list[str] = []
    idx = 1
    for row in timing_rows or []:
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        start = float(row.get("start") or 0.0) + float(intro_offset)
        dur = float(row.get("duration") or row.get("tts_duration") or 0.0)
        if dur <= 0:
            continue
        end = start + dur
        blocks.append(
            f"{idx}\n{_srt_timestamp(start)} --> {_srt_timestamp(end)}\n{text}\n"
        )
        idx += 1
    return "\n".join(blocks).rstrip() + ("\n" if blocks else "")


def write_srt_sidecar(
    video_path: str | Path,
    timing_rows: list[dict[str, Any]],
    *,
    intro_offset: float = 0.0,
) -> str | None:
    """Write `<video_stem>.srt` next to the MP4. Returns path or None if empty."""
    srt_body = timing_rows_to_srt(timing_rows, intro_offset=intro_offset)
    if not srt_body.strip():
        return None
    out = Path(video_path).with_suffix(".srt")
    out.write_text(srt_body, encoding="utf-8")
    return str(out)
