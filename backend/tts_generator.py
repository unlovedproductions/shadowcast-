"""
ShadowCast — TTS (Text-to-Speech) Generator Module
Supports multiple TTS providers:
  1. gTTS (Google TTS) — free, online, decent quality
  2. Kokoro TTS — free, LOCAL, high quality (requires kokoro-onnx install)
  3. Piper TTS — free, LOCAL, fast (requires piper-tts install)
  4. OpenAI TTS — paid, highest quality (requires API key)

Provider selection is automatic based on what's installed, or can be forced.

When audio_driven=True (default), segment visuals follow measured speech length
plus an intentional pause — speech is never trimmed to fit LLM duration guesses.
"""

import json
import os
import tempfile
import subprocess
import threading

from moviepy import AudioClip, AudioFileClip, VideoFileClip, concatenate_audioclips
from moviepy.audio.fx import AudioFadeIn, AudioFadeOut


_PROVIDERS_CACHE = None
_PROVIDERS_LOCK = threading.Lock()
_KOKORO_INSTANCE = None
_KOKORO_LOCK = threading.Lock()

# Research default: 200–500ms breath/cut padding between segments.
_DEFAULT_INTER_SEGMENT_PAUSE = 0.35
_CROSSFADE_SECONDS = 0.04
_MIN_SEGMENT_DURATION = 0.12


# ── Provider Detection ───────────────────────────────────────────────
def _check_kokoro():
    try:
        import kokoro_onnx  # noqa: F401
        return True
    except ImportError:
        return False

def _check_piper():
    try:
        result = subprocess.run(["piper", "--help"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def _check_openai_tts():
    try:
        from openai import OpenAI  # noqa: F401
        key = os.environ.get("OPENAI_API_KEY", "")
        return bool(key)
    except ImportError:
        return False

def _check_gtts():
    try:
        from gtts import gTTS  # noqa: F401
        return True
    except ImportError:
        return False


def get_available_providers(force_refresh: bool = False):
    """Return list of available TTS providers with status (cached per process)."""
    global _PROVIDERS_CACHE
    with _PROVIDERS_LOCK:
        if _PROVIDERS_CACHE is not None and not force_refresh:
            return _PROVIDERS_CACHE
        providers = {
            "kokoro": {
                "name": "Kokoro TTS",
                "available": _check_kokoro(),
                "type": "local",
                "quality": "high",
                "cost": "free",
                "install": "pip install kokoro-onnx",
                "description": "High-quality local TTS. Runs on your GPU. Best free option.",
                "voices": ["af_bella", "af_sarah", "am_adam", "am_michael", "bf_emma", "bm_george"],
            },
            "piper": {
                "name": "Piper TTS",
                "available": _check_piper(),
                "type": "local",
                "quality": "medium",
                "cost": "free",
                "install": "pip install piper-tts",
                "description": "Fast local TTS. Lower quality but very fast inference.",
                "voices": ["en_US-lessac-medium", "en_US-amy-medium", "en_US-ryan-medium"],
            },
            "openai": {
                "name": "OpenAI TTS",
                "available": _check_openai_tts(),
                "type": "cloud",
                "quality": "highest",
                "cost": "paid (~$0.015/1K chars)",
                "install": "pip install openai (+ API key)",
                "description": "Best quality. Costs ~1.5 cents per 1000 characters.",
                "voices": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
            },
            "gtts": {
                "name": "Google TTS",
                "available": _check_gtts(),
                "type": "cloud",
                "quality": "basic",
                "cost": "free",
                "install": "pip install gtts",
                "description": "Free online TTS. Basic quality but always works.",
                "voices": ["en"],
            },
        }
        _PROVIDERS_CACHE = providers
        return providers


def get_best_provider():
    """Return the best available provider in quality order."""
    providers = get_available_providers()
    for provider in ["kokoro", "openai", "piper", "gtts"]:
        if providers[provider]["available"]:
            return provider
    return "gtts"  # fallback


def _get_kokoro():
    """Lazily load and reuse a single Kokoro model instance. Caller must hold _KOKORO_LOCK."""
    global _KOKORO_INSTANCE
    if _KOKORO_INSTANCE is None:
        import kokoro_onnx
        _KOKORO_INSTANCE = kokoro_onnx.Kokoro("kokoro-v0_19.onnx", "voices.bin")
    return _KOKORO_INSTANCE


# ── TTS Generation by Provider ──────────────────────────────────────

def _generate_gtts(text: str, output_path: str, voice: str = "en"):
    """Generate audio using Google TTS."""
    from gtts import gTTS
    tts = gTTS(text=text, lang=voice, slow=False)
    tts.save(output_path)


def _generate_kokoro(text: str, output_path: str, voice: str = "af_bella"):
    """Generate audio using Kokoro TTS (local, GPU-accelerated)."""
    import soundfile as sf

    with _KOKORO_LOCK:
        kokoro = _get_kokoro()
        samples, sample_rate = kokoro.create(text, voice=voice, speed=1.0)
    sf.write(output_path, samples, sample_rate)


def _generate_piper(text: str, output_path: str, voice: str = "en_US-lessac-medium"):
    """Generate audio using Piper TTS (local, CPU-based)."""
    process = subprocess.run(
        ["piper", "--model", voice, "--output_file", output_path],
        input=text.encode("utf-8"),
        capture_output=True,
        timeout=60,
    )
    if process.returncode != 0:
        raise RuntimeError(f"Piper TTS failed: {process.stderr.decode()}")


def _generate_openai_tts(text: str, output_path: str, voice: str = "onyx"):
    """Generate audio using OpenAI TTS API."""
    from openai import OpenAI
    client = OpenAI()
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
    )
    response.stream_to_file(output_path)


# ── Provider Dispatch ────────────────────────────────────────────────

PROVIDER_GENERATORS = {
    "gtts": _generate_gtts,
    "kokoro": _generate_kokoro,
    "piper": _generate_piper,
    "openai": _generate_openai_tts,
}

DEFAULT_VOICES = {
    "gtts": "en",
    "kokoro": "af_bella",
    "piper": "en_US-lessac-medium",
    "openai": "onyx",
}


def _silence_clip(duration: float, fps: int = 44100):
    duration = max(float(duration or 0.0), 0.0)
    if duration <= 0:
        return None
    return AudioClip(lambda t: 0 * t, duration=duration, fps=fps)


def _inter_segment_pause() -> float:
    raw = os.getenv("SHADOWCAST_TTS_INTER_SEGMENT_PAUSE", str(_DEFAULT_INTER_SEGMENT_PAUSE))
    try:
        pause = float(raw or _DEFAULT_INTER_SEGMENT_PAUSE)
    except (TypeError, ValueError):
        pause = _DEFAULT_INTER_SEGMENT_PAUSE
    return max(0.0, min(pause, 1.0))


def _with_edge_fades(clip, fade_seconds: float = _CROSSFADE_SECONDS):
    """Micro fades reduce click/seam artifacts when concatenating TTS segments."""
    fade = max(0.0, float(fade_seconds or 0.0))
    if fade <= 0 or clip.duration <= fade * 2:
        return clip
    return clip.with_effects([AudioFadeIn(fade), AudioFadeOut(fade)])


def generate_segment_audio(text: str, output_path: str,
                           provider: str = "auto", voice: str = None) -> str:
    """Generate audio for a single text segment."""
    if provider == "auto":
        provider = get_best_provider()

    if voice is None:
        voice = DEFAULT_VOICES.get(provider, "en")

    generator = PROVIDER_GENERATORS.get(provider)
    if not generator:
        raise ValueError(f"Unknown TTS provider: {provider}")

    # Clean text of emoji
    clean_text = "".join(c for c in text if ord(c) < 0x1F600 or ord(c) > 0x1F9FF)
    clean_text = clean_text.strip()
    if not clean_text:
        return output_path

    generator(clean_text, output_path, voice)
    return output_path


def apply_timing_to_segments(segments: list, timing_rows: list) -> float:
    """Write measured TTS durations onto segment dicts. Returns total duration."""
    total = 0.0
    for row in timing_rows:
        idx = int(row["index"])
        if idx < 0 or idx >= len(segments):
            continue
        seg = segments[idx]
        dur = float(row["duration"])
        seg["duration"] = round(dur, 3)
        seg["tts_duration"] = round(float(row["tts_duration"]), 3)
        seg["tts_pause"] = round(float(row.get("pause", 0.0)), 3)
        total += dur
    return total


def apply_timing_to_script(script: dict, timing_rows: list) -> dict:
    """
    Apply a shared TTS timing clock to the script in place.

    timing_rows are ordered across short-form segments or flattened chapter segments.
    """
    if "chapters" in script:
        flat = []
        for chapter in script.get("chapters", []):
            flat.extend(chapter.get("segments", []))
        apply_timing_to_segments(flat, timing_rows)
    else:
        apply_timing_to_segments(script.get("segments", []), timing_rows)

    total = sum(float(r["duration"]) for r in timing_rows)
    script["total_duration_seconds"] = round(total, 3)
    script["tts_timing"] = timing_rows
    return script


def resolve_tts_timing(script: dict, voiceover_path: str | None = None) -> list:
    """Return timing rows from script.tts_timing or voiceover_timing sidecar."""
    rows = script.get("tts_timing")
    if isinstance(rows, list) and rows:
        return rows
    candidates = []
    if voiceover_path:
        candidates.append(os.path.splitext(voiceover_path)[0] + "_timing.json")
    hook = script.get("hook_type", "unknown")
    fmt = script.get("format", "short_form")
    if voiceover_path:
        base_dir = os.path.dirname(voiceover_path) or "."
        candidates.append(os.path.join(base_dir, f"{hook}_{fmt}_voiceover_timing.json"))
    for path in candidates:
        if not path or not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            loaded = data.get("segments") if isinstance(data, dict) else None
            if isinstance(loaded, list) and loaded:
                script["tts_timing"] = loaded
                return loaded
        except (OSError, json.JSONDecodeError, TypeError):
            continue
    return []


def _write_timing_sidecar(output_path: str, timing_rows: list) -> str:
    sidecar = os.path.splitext(output_path)[0] + "_timing.json"
    payload = {
        "segments": timing_rows,
        "total_duration_seconds": round(sum(float(r["duration"]) for r in timing_rows), 3),
    }
    with open(sidecar, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return sidecar


# ── Main Functions ───────────────────────────────────────────────────

def generate_voiceover_for_segments(segments: list, output_path: str,
                                     provider: str = "auto",
                                     voice: str = None,
                                     lang: str = "en",
                                     audio_driven: bool = True,
                                     apply_durations: bool = True,
                                     write_timing: bool = True) -> tuple[str, list]:
    """
    Generate a single voiceover from script segments.

    audio_driven=True (default): never trim speech to LLM duration guesses.
    Scene length becomes measured TTS duration + inter-segment pause.
    Returns (output_path, timing_rows) where timing_rows form the shared clock
    for captions / overlays.
    """
    if provider == "auto":
        provider = get_best_provider()

    # For backward compatibility, lang maps to gtts voice
    if provider == "gtts" and voice is None:
        voice = lang

    temp_files = []
    audio_clips = []
    timing_rows = []
    target_pause = _inter_segment_pause()
    cumulative = 0.0

    try:
        for i, seg in enumerate(segments):
            text = seg.get("text", "").strip()
            if not text:
                continue

            suffix = ".wav" if provider in ("kokoro", "piper") else ".mp3"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            temp_files.append(tmp.name)
            tmp.close()

            try:
                generate_segment_audio(text, tmp.name, provider=provider, voice=voice)
                clip = AudioFileClip(tmp.name)
            except Exception as e:
                print(f"TTS segment {i} failed ({provider}): {e}")
                # Try fallback to gtts
                if provider != "gtts":
                    try:
                        fallback_tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                        temp_files.append(fallback_tmp.name)
                        fallback_tmp.close()
                        _generate_gtts(text, fallback_tmp.name)
                        clip = AudioFileClip(fallback_tmp.name)
                        print(f"  Fell back to gTTS for segment {i}")
                    except Exception as e2:
                        print(f"  gTTS fallback also failed: {e2}")
                        continue
                else:
                    continue

            tts_duration = float(clip.duration or 0.0)
            llm_duration = 0.0
            try:
                llm_duration = float(seg.get("duration", 0) or 0)
            except (TypeError, ValueError):
                llm_duration = 0.0

            if audio_driven:
                pause = target_pause
                segment_duration = max(tts_duration + pause, _MIN_SEGMENT_DURATION)
                # Never trim speech — only pad trailing silence to the segment slot.
                clip = _with_edge_fades(clip)
                audio_clips.append(clip)
                remaining = max(segment_duration - tts_duration, 0.0)
                silence = _silence_clip(remaining, int(getattr(clip, "fps", 44100) or 44100))
                if silence:
                    audio_clips.append(silence)
            else:
                # Legacy: force speech into LLM slot (can cut words).
                segment_duration = llm_duration if llm_duration > 0 else max(tts_duration + target_pause, _MIN_SEGMENT_DURATION)
                max_voice_duration = max(segment_duration - target_pause, _MIN_SEGMENT_DURATION)
                if clip.duration > max_voice_duration:
                    trimmed = clip.subclipped(0, max_voice_duration)
                    clip.close()
                    clip = trimmed
                    tts_duration = float(clip.duration or 0.0)
                clip = _with_edge_fades(clip)
                audio_clips.append(clip)
                remaining = max(segment_duration - clip.duration, target_pause)
                silence = _silence_clip(remaining, int(getattr(clip, "fps", 44100) or 44100))
                if silence:
                    audio_clips.append(silence)

            row = {
                "index": i,
                "text": text,
                "start": round(cumulative, 3),
                "tts_duration": round(tts_duration, 3),
                "pause": round(max(segment_duration - tts_duration, 0.0), 3),
                "duration": round(segment_duration, 3),
                "llm_duration": round(llm_duration, 3) if llm_duration else None,
            }
            timing_rows.append(row)
            cumulative += segment_duration

        if apply_durations and timing_rows:
            apply_timing_to_segments(segments, timing_rows)

        if audio_clips:
            final_audio = concatenate_audioclips(audio_clips)
            final_audio.write_audiofile(output_path, logger=None)
            final_audio.close()

        for clip in audio_clips:
            try:
                clip.close()
            except Exception:
                pass

        if write_timing and timing_rows:
            _write_timing_sidecar(output_path, timing_rows)

    finally:
        for f in temp_files:
            try:
                os.unlink(f)
            except Exception:
                pass

    return output_path, timing_rows


def add_voiceover_to_video(video_path: str, audio_path: str, output_path: str) -> str:
    """Combine a rendered video with a voiceover audio track."""
    video = VideoFileClip(video_path)
    audio = AudioFileClip(audio_path)

    clip_refs = [audio]

    # Trim or pad audio to match video duration.
    if audio.duration > video.duration:
        audio = audio.subclipped(0, video.duration)
        clip_refs.append(audio)
    elif audio.duration < video.duration:
        silence = _silence_clip(video.duration - audio.duration, int(getattr(audio, "fps", 44100) or 44100))
        if silence:
            clip_refs.append(silence)
            padded = concatenate_audioclips([audio, silence])
            clip_refs.append(padded)
            audio = padded

    video_with_audio = video.with_audio(audio)
    video_with_audio.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        logger=None,
    )

    video.close()
    for ref in reversed(clip_refs):
        try:
            ref.close()
        except Exception:
            pass
    video_with_audio.close()

    return output_path


def generate_voiceover_for_script(script: dict, output_dir: str,
                                   provider: str = "auto",
                                   voice: str = None,
                                   audio_driven: bool = True) -> tuple[str, list]:
    """Generate voiceover for a complete script (short or long form).

    Returns (audio_path, timing_rows). Mutates script segment durations when
    audio_driven is True so the renderer can build visuals to the same clock.
    """
    os.makedirs(output_dir, exist_ok=True)

    hook_type = script.get("hook_type", "unknown")
    fmt = script.get("format", "short_form")

    # Collect all segments (flat list shares objects with script for in-place updates)
    if "chapters" in script:
        segments = []
        for chapter in script["chapters"]:
            segments.extend(chapter.get("segments", []))
    else:
        segments = script.get("segments", [])

    audio_path = os.path.join(output_dir, f"{hook_type}_{fmt}_voiceover.mp3")
    audio_path, timing_rows = generate_voiceover_for_segments(
        segments,
        audio_path,
        provider=provider,
        voice=voice,
        audio_driven=audio_driven,
        apply_durations=audio_driven,
        write_timing=True,
    )
    if audio_driven and timing_rows:
        apply_timing_to_script(script, timing_rows)

    return audio_path, timing_rows


if __name__ == "__main__":
    print("ShadowCast TTS Provider Status:")
    print("=" * 50)
    providers = get_available_providers()
    for key, info in providers.items():
        status = "✓ AVAILABLE" if info["available"] else "✗ Not installed"
        print(f"  {info['name']:20s} [{info['type']:6s}] {status}")
        if not info["available"]:
            print(f"    Install: {info['install']}")
    print(f"\nBest available: {get_best_provider()}")

    # Quick test with best provider
    test_segments = [
        {"text": "This changes everything", "duration": 1.0},
        {"text": "The number one gadget of 2025", "duration": 1.0},
        {"text": "Check the link in description", "duration": 1.0},
    ]

    out = os.path.join(os.path.dirname(__file__), "output", "test_voiceover.mp3")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    provider = get_best_provider()
    print(f"\nGenerating test voiceover with {provider}...")
    path, timing = generate_voiceover_for_segments(test_segments, out, provider=provider)
    print(f"✓ Test voiceover saved to {path}")
    print(f"  Timing: {timing}")
    print(f"  Updated durations: {[s.get('duration') for s in test_segments]}")
