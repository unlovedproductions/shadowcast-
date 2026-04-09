"""
ShadowCast — TTS (Text-to-Speech) Generator Module
Supports multiple TTS providers:
  1. gTTS (Google TTS) — free, online, decent quality
  2. Kokoro TTS — free, LOCAL, high quality (requires kokoro-onnx install)
  3. Piper TTS — free, LOCAL, fast (requires piper-tts install)
  4. OpenAI TTS — paid, highest quality (requires API key)

Provider selection is automatic based on what's installed, or can be forced.
"""

import json
import os
import tempfile
import subprocess

from moviepy.editor import AudioFileClip, VideoFileClip, CompositeAudioClip, concatenate_audioclips


# ── Provider Detection ───────────────────────────────────────────────
def _check_kokoro():
    try:
        import kokoro_onnx
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
        from openai import OpenAI
        key = os.environ.get("OPENAI_API_KEY", "")
        return bool(key)
    except ImportError:
        return False

def _check_gtts():
    try:
        from gtts import gTTS
        return True
    except ImportError:
        return False


def get_available_providers():
    """Return list of available TTS providers with status."""
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
    return providers


def get_best_provider():
    """Return the best available provider in quality order."""
    for provider in ["kokoro", "openai", "piper", "gtts"]:
        providers = get_available_providers()
        if providers[provider]["available"]:
            return provider
    return "gtts"  # fallback


# ── TTS Generation by Provider ──────────────────────────────────────

def _generate_gtts(text: str, output_path: str, voice: str = "en"):
    """Generate audio using Google TTS."""
    from gtts import gTTS
    tts = gTTS(text=text, lang=voice, slow=False)
    tts.save(output_path)


def _generate_kokoro(text: str, output_path: str, voice: str = "af_bella"):
    """Generate audio using Kokoro TTS (local, GPU-accelerated)."""
    import kokoro_onnx
    import soundfile as sf

    kokoro = kokoro_onnx.Kokoro("kokoro-v0_19.onnx", "voices.bin")
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


# ── Main Functions ───────────────────────────────────────────────────

def generate_voiceover_for_segments(segments: list, output_path: str,
                                     provider: str = "auto",
                                     voice: str = None,
                                     lang: str = "en") -> str:
    """Generate a single voiceover audio file from script segments."""
    if provider == "auto":
        provider = get_best_provider()

    # For backward compatibility, lang maps to gtts voice
    if provider == "gtts" and voice is None:
        voice = lang

    temp_files = []
    audio_clips = []

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
                audio_clips.append(clip)
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
                        audio_clips.append(clip)
                        print(f"  Fell back to gTTS for segment {i}")
                    except Exception as e2:
                        print(f"  gTTS fallback also failed: {e2}")

        if audio_clips:
            final_audio = concatenate_audioclips(audio_clips)
            final_audio.write_audiofile(output_path, logger=None)
            final_audio.close()

        for clip in audio_clips:
            clip.close()

    finally:
        for f in temp_files:
            try:
                os.unlink(f)
            except Exception:
                pass

    return output_path


def add_voiceover_to_video(video_path: str, audio_path: str, output_path: str) -> str:
    """Combine a rendered video with a voiceover audio track."""
    video = VideoFileClip(video_path)
    audio = AudioFileClip(audio_path)

    # Trim audio to match video duration
    if audio.duration > video.duration:
        audio = audio.subclipped(0, video.duration)

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
    audio.close()
    video_with_audio.close()

    return output_path


def generate_voiceover_for_script(script: dict, output_dir: str,
                                   provider: str = "auto",
                                   voice: str = None) -> str:
    """Generate voiceover for a complete script (short or long form)."""
    os.makedirs(output_dir, exist_ok=True)

    hook_type = script.get("hook_type", "unknown")
    fmt = script.get("format", "short_form")

    # Collect all segments
    if "chapters" in script:
        segments = []
        for chapter in script["chapters"]:
            segments.extend(chapter.get("segments", []))
    else:
        segments = script.get("segments", [])

    audio_path = os.path.join(output_dir, f"{hook_type}_{fmt}_voiceover.mp3")
    generate_voiceover_for_segments(segments, audio_path, provider=provider, voice=voice)

    return audio_path


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
        {"text": "This changes everything"},
        {"text": "The number one gadget of 2025"},
        {"text": "Check the link in description"},
    ]

    out = os.path.join(os.path.dirname(__file__), "output", "test_voiceover.mp3")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    provider = get_best_provider()
    print(f"\nGenerating test voiceover with {provider}...")
    generate_voiceover_for_segments(test_segments, out, provider=provider)
    print(f"✓ Test voiceover saved to {out}")
