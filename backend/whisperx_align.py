"""Optional WhisperX forced-align for Shorts word highlights.

Enable with ``SHADOWCAST_WHISPERX_ALIGN=1``. Requires the optional ``whisperx``
package (and its torch/CUDA stack). When unavailable or align fails, callers
must fall back to proportional chunk timing.
"""

from __future__ import annotations

import os
from typing import Any


def whisperx_align_enabled() -> bool:
    raw = (os.getenv("SHADOWCAST_WHISPERX_ALIGN") or "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def whisperx_available() -> bool:
    try:
        import whisperx  # noqa: F401
    except Exception:
        return False
    return True


def align_words_to_audio(
    audio_path: str,
    transcript: str,
    *,
    language: str = "en",
    device: str | None = None,
) -> list[dict[str, Any]] | None:
    """
    Return ``[{word, start, end}, ...]`` using WhisperX forced alignment.

    Returns None when disabled, missing deps, or alignment fails.
    """
    if not whisperx_align_enabled():
        return None
    if not audio_path or not os.path.isfile(audio_path):
        return None
    text = " ".join(str(transcript or "").split())
    if not text:
        return None
    try:
        import whisperx
    except Exception:
        return None

    try:
        import torch

        resolved_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    except Exception:
        resolved_device = device or "cpu"

    try:
        audio = whisperx.load_audio(audio_path)
        align_model, metadata = whisperx.load_align_model(
            language_code=language,
            device=resolved_device,
        )
        # Single-segment forced align against the known TTS transcript.
        result = whisperx.align(
            [{"text": text, "start": 0.0, "end": max(0.1, len(audio) / 16000.0)}],
            align_model,
            metadata,
            audio,
            resolved_device,
            return_char_alignments=False,
        )
        words_out: list[dict[str, Any]] = []
        for seg in result.get("segments") or []:
            for w in seg.get("words") or []:
                word = str(w.get("word") or "").strip()
                if not word:
                    continue
                start = w.get("start")
                end = w.get("end")
                if start is None or end is None:
                    continue
                words_out.append(
                    {
                        "word": word,
                        "start": float(start),
                        "end": float(end),
                    }
                )
        return words_out or None
    except Exception as exc:
        print(f"Warning: WhisperX align failed ({exc}); using proportional highlights")
        return None


def refine_caption_events_with_word_align(
    chunk_events: list[dict[str, Any]],
    word_timings: list[dict[str, Any]],
    *,
    intro_offset: float = 0.0,
    min_word_dur: float = 0.10,
) -> list[dict[str, Any]] | None:
    """
    Rebuild karaoke highlight frames from forced-align word clocks.

    Matches words in order across chunk events. Returns None if alignment
    coverage is too sparse to trust.
    """
    if not chunk_events or not word_timings:
        return None

    flat_words: list[str] = []
    for ev in chunk_events:
        flat_words.extend(str(ev.get("text") or "").split())
    if not flat_words:
        return None

    aligned = list(word_timings)
    if len(aligned) < max(1, int(len(flat_words) * 0.6)):
        return None

    # Consume aligned words in order for each chunk.
    idx = 0
    out: list[dict[str, Any]] = []
    for ev in chunk_events:
        words = str(ev.get("text") or "").split()
        text = " ".join(words)
        if not words:
            continue
        base = {"text": text, "segment_index": ev.get("segment_index")}
        if len(words) == 1:
            if idx < len(aligned):
                w = aligned[idx]
                idx += 1
                start = float(intro_offset) + float(w["start"])
                dur = max(min_word_dur, float(w["end"]) - float(w["start"]))
                out.append(
                    {
                        **base,
                        "start": round(start, 3),
                        "duration": round(dur, 3),
                        "highlight_index": 0,
                    }
                )
            else:
                out.append(
                    {
                        **base,
                        "start": round(float(ev.get("start", 0.0) or 0.0), 3),
                        "duration": round(float(ev.get("duration", 0.0) or 0.0), 3),
                        "highlight_index": 0,
                    }
                )
            continue

        chunk_word_times: list[tuple[float, float]] = []
        for _ in words:
            if idx >= len(aligned):
                return None
            w = aligned[idx]
            idx += 1
            chunk_word_times.append((float(w["start"]), float(w["end"])))

        for i, (w_start, w_end) in enumerate(chunk_word_times):
            start = float(intro_offset) + w_start
            dur = max(min_word_dur, w_end - w_start)
            out.append(
                {
                    **base,
                    "start": round(start, 3),
                    "duration": round(dur, 3),
                    "highlight_index": i,
                }
            )
    return out or None
