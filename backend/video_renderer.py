"""
ShadowCast Video Renderer — v2.0
Renders script JSON into MP4 videos with kinetic typography, real transitions,
branded overlays, progress tracking, and engagement bait moments.
Supports both short-form (9:16) and long-form (16:9) formats.
"""

import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import textwrap
from contextlib import contextmanager
from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy import (
    ImageClip,
    CompositeVideoClip,
    TextClip,
    ColorClip,
    AudioFileClip,
    concatenate_videoclips,
    vfx,
)
from moviepy import config as moviepy_config

# Import new modules
from brand_overlays import (
    render_branded_intro,
    render_branded_outro,
    render_watermark_overlay,
    render_lower_third,
    render_progress_overlay,
    render_section_header,
    render_poll_card,
    render_comment_prompt,
    render_subscribe_card,
    caption_events_from_timing,
    expand_caption_word_highlights,
    lower_third_event_from_timing,
    render_shorts_caption,
    shorts_word_highlight_enabled,
    longform_burnin_captions_enabled,
)
from sound_design import (
    generate_background_music,
    generate_sfx,
    mix_audio,
    add_audio_to_video,
    SAMPLE_RATE as AUDIO_SAMPLE_RATE,
)
from audio_options import MOOD_TEMPO, resolve_audio_mood
from product_media import frame_with_product_hero, segment_wants_product_hero
from scipy.io.wavfile import read as read_wav
from caption_srt import write_srt_sidecar
from broll import make_broll_clip
from tts_generator import generate_voiceover_for_script, resolve_tts_timing
from whisperx_align import (
    align_words_to_audio,
    refine_caption_events_with_word_align,
    whisperx_align_enabled,
)

from comparison_layouts import (
    render_vs_split_screen,
    render_spec_comparison,
    render_scorecard,
    render_price_comparison,
    render_winner_reveal,
)
from content_styles import normalize_content_style
from video_claims import SHORT_FORM, LONG_FORM, build_render_timeline

from kinetic_effects import (
    create_word_by_word_clip,
    create_typewriter_clip,
    create_impact_scale_clip,
    create_highlight_sweep_clip,
    create_shake_clip,
    create_slide_up_clip,
    create_slide_left_clip,
    create_glitch_transition,
    create_flash_transition,
    create_swipe_transition,
    create_zoom_transition,
)

# ── Paths ──────────────────────────────────────────────────────────────
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
_VALID_VIDEO_PRESETS = {
    "ultrafast", "superfast", "veryfast", "faster", "fast",
    "medium", "slow", "slower", "veryslow",
}
_NVENC_PRESET_MAP = {
    "ultrafast": "p1",
    "superfast": "p1",
    "veryfast": "p2",
    "faster": "p3",
    "fast": "p4",
    "medium": "p4",
    "slow": "p5",
    "slower": "p6",
    "veryslow": "p7",
}
VIDEO_RENDER_PRESET = os.getenv("SHADOWCAST_VIDEO_PRESET", "medium").strip().lower()
if VIDEO_RENDER_PRESET not in _VALID_VIDEO_PRESETS:
    VIDEO_RENDER_PRESET = "medium"
_nvenc_available: bool | None = None


def resolve_video_preset(preset: str | None = None) -> str:
    candidate = (preset or VIDEO_RENDER_PRESET or "medium").strip().lower()
    if candidate not in _VALID_VIDEO_PRESETS:
        return VIDEO_RENDER_PRESET
    return candidate


def moviepy_ffmpeg_binary() -> str:
    """FFmpeg binary MoviePy will invoke for encode."""
    binary = getattr(moviepy_config, "FFMPEG_BINARY", None)
    if binary and binary not in ("unset", "ffmpeg-imageio", "auto-detect"):
        return binary
    return shutil.which("ffmpeg") or "ffmpeg"


def system_ffmpeg_binary() -> str | None:
    return shutil.which("ffmpeg")


def ffmpeg_lists_nvenc(binary: str) -> bool:
    """True when the given ffmpeg binary lists the h264_nvenc encoder."""
    try:
        proc = subprocess.run(
            [binary, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        blob = f"{proc.stdout or ''}{proc.stderr or ''}"
        return "h264_nvenc" in blob
    except Exception:
        return False


def bind_moviepy_ffmpeg_binary(binary: str) -> None:
    """Point MoviePy at a specific ffmpeg (needed when imageio's build lacks NVENC)."""
    os.environ["FFMPEG_BINARY"] = binary
    moviepy_config.FFMPEG_BINARY = binary


def ensure_moviepy_nvenc_ffmpeg() -> bool:
    """
    Ensure MoviePy's ffmpeg can do h264_nvenc.

    imageio's bundled ffmpeg often lacks NVENC while system /usr/bin/ffmpeg has it.
    Rebind MoviePy to the system binary when that mismatch would break encode.
    """
    current = moviepy_ffmpeg_binary()
    if ffmpeg_lists_nvenc(current):
        return True
    system = system_ffmpeg_binary()
    if not system:
        return False
    try:
        same = os.path.samefile(current, system)
    except OSError:
        same = os.path.abspath(current) == os.path.abspath(system)
    if same:
        return False
    if not ffmpeg_lists_nvenc(system):
        return False
    bind_moviepy_ffmpeg_binary(system)
    return True


def ffmpeg_has_nvenc() -> bool:
    """True when the ffmpeg MoviePy will use lists h264_nvenc (cached)."""
    global _nvenc_available
    if _nvenc_available is not None:
        return _nvenc_available
    _nvenc_available = ensure_moviepy_nvenc_ffmpeg()
    return _nvenc_available


def resolve_write_videofile_kwargs(preset: str | None = None) -> dict[str, Any]:
    """
    MoviePy write_videofile kwargs for final encode.

    SHADOWCAST_FFMPEG_CODEC=auto|libx264|h264_nvenc
    auto uses NVENC when the MoviePy ffmpeg reports h264_nvenc
    (rebinding to system ffmpeg when the imageio bundle lacks it).
    """
    render_preset = resolve_video_preset(preset)
    codec_pref = os.getenv("SHADOWCAST_FFMPEG_CODEC", "auto").strip().lower()
    force_software = codec_pref in ("libx264", "x264", "software", "cpu")
    force_nvenc = codec_pref in ("h264_nvenc", "nvenc")
    nvenc_ready = False if force_software else ffmpeg_has_nvenc()
    if force_nvenc and not nvenc_ready:
        # Best-effort rebind even when the cached probe said no.
        ensure_moviepy_nvenc_ffmpeg()
    use_nvenc = force_nvenc or (not force_software and codec_pref in ("", "auto") and nvenc_ready)
    if use_nvenc:
        return {
            "codec": "h264_nvenc",
            "preset": _NVENC_PRESET_MAP.get(render_preset, "p4"),
            "ffmpeg_params": ["-rc", "vbr", "-cq", "23", "-b:v", "0", "-pix_fmt", "yuv420p"],
            "threads": 4,
        }
    return {
        "codec": "libx264",
        "preset": render_preset,
        "ffmpeg_params": ["-pix_fmt", "yuv420p"],
        "threads": 4,
    }

FONT_BOLD = os.path.join(ASSETS_DIR, "Montserrat-Bold.ttf")
FONT_EXTRABOLD = os.path.join(ASSETS_DIR, "Montserrat-ExtraBold.ttf")
FONT_BLACK = os.path.join(ASSETS_DIR, "Montserrat-Black.ttf")
FONT_REGULAR = os.path.join(ASSETS_DIR, "Montserrat-Regular.ttf")

# Fallback when Montserrat assets are absent on the deploy host
if not os.path.exists(FONT_BOLD):
    print(f"Warning: Montserrat fonts missing under {ASSETS_DIR}; falling back to NotoSans")
    FONT_BOLD = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
    FONT_EXTRABOLD = "/usr/share/fonts/truetype/noto/NotoSans-Black.ttf"
    FONT_BLACK = "/usr/share/fonts/truetype/noto/NotoSans-Black.ttf"
    FONT_REGULAR = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"

# ── ShadowCast Brand Palette (locked) ─────────────────────────────────
BRAND_BG = (10, 10, 15)
BRAND_ACCENT = (196, 80, 122)  # #c4507a dark pink

# ── Style mappings ─────────────────────────────────────────────────────
STYLE_FONT_MAP = {
    "headline_bold": (FONT_BLACK, 1.3),
    "subtitle": (FONT_REGULAR, 0.75),
    "accent_pop": (FONT_EXTRABOLD, 1.15),
    "cta_button": (FONT_EXTRABOLD, 1.0),
    "stat_number": (FONT_BLACK, 1.5),
    "question": (FONT_BOLD, 1.0),
    "pros": (FONT_BOLD, 0.85),
    "cons": (FONT_BOLD, 0.85),
    "pro_point": (FONT_BOLD, 0.85),
    "con_point": (FONT_BOLD, 0.85),
    "comparison": (FONT_BOLD, 0.9),
    "scorecard": (FONT_BOLD, 0.9),
    "elimination": (FONT_BOLD, 0.85),
    "verdict": (FONT_BLACK, 1.2),
}

TEXT_STYLE_ALIASES = {
    "pro_point": "pros",
    "con_point": "cons",
}


def normalize_text_style(text_style: str) -> str:
    return TEXT_STYLE_ALIASES.get(text_style, text_style)


def compute_render_fingerprint(script: dict, *, fmt: str, render_options: dict | None = None) -> str:
    """Stable hash of enriched script + render-affecting options for cache invalidation."""
    payload = {
        "fmt": fmt,
        "script": script,
        "options": render_options or {},
    }
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fingerprint_seed(fingerprint: str) -> int:
    return int(fingerprint[:16], 16) % (2**32 - 1)


@contextmanager
def _seeded_render_rng(seed: int | None):
    """Temporarily seed module RNGs for reproducible visuals/audio."""
    if seed is None:
        yield
        return
    py_state = random.getstate()
    np_state = np.random.get_state()
    random.seed(seed)
    np.random.seed(seed)
    try:
        yield
    finally:
        random.setstate(py_state)
        np.random.set_state(np_state)


def _terminal_frame_from_clip(clip, width: int, height: int, fallback_frame: np.ndarray) -> np.ndarray:
    """Best-effort last frame for transitions; falls back to provided static frame."""
    try:
        t = max(float(getattr(clip, "duration", 0.0) or 0.0) - 1e-3, 0.0)
        frame = clip.get_frame(t)
        if frame is None:
            return fallback_frame
        arr = np.asarray(frame)
        if arr.ndim == 3 and arr.shape[0] == height and arr.shape[1] == width:
            if arr.shape[2] == 4:
                return arr[:, :, :3]
            return arr
    except Exception:
        pass
    return fallback_frame


def _make_progress_animator(width: int, height: int, duration: float, accent_color: tuple):
    """Cached progress bar: no full-HD PIL redraw per frame."""
    bar_height = max(1, int(height * 0.01))
    accent = np.array([*accent_color, 255], dtype=np.uint8)
    empty = np.zeros((height, width, 4), dtype=np.uint8)

    def make_frame(t):
        progress = 0.0 if duration <= 0 else min(1.0, max(0.0, float(t) / duration))
        filled = max(1, int(width * progress)) if progress > 0 else 0
        frame = empty.copy()
        if filled:
            frame[height - bar_height :, :filled] = accent
        return frame

    return ImageClip(make_frame(0), duration=duration).transform(lambda get_frame, t: make_frame(t))


def _schedule_sfx_from_timeline(timeline: dict, is_short: bool) -> list:
    sfx_list = []
    events = timeline.get("segment_events", [])
    if not is_short:
        for chrome in timeline.get("chrome_events", []):
            if chrome.get("kind") == "chapter_card":
                sfx_list.append((generate_sfx("ding", duration=0.5, amplitude=0.5), chrome["start"]))

    for event in events:
        seg = event["segment"]
        current_time = float(event["start"])
        seg_dur = float(event["duration"])
        anim = seg.get("animation", "fade_in")
        trans = event.get("transition") or seg.get("transition_to_next", "fade")
        amp_anim = 0.4 if is_short else 0.3
        amp_trans = 0.5 if is_short else 0.4

        if anim in ("word_by_word", "typewriter"):
            sfx_list.append((generate_sfx("pop", duration=0.1, amplitude=amp_anim), current_time + 0.1))
        elif anim in ("impact_scale", "shake"):
            sfx_list.append((generate_sfx("bass_drop", duration=0.8, amplitude=amp_anim + 0.1), current_time))
        elif anim in ("slide_up", "slide_left"):
            sfx_list.append((generate_sfx("swoosh", duration=0.4, amplitude=amp_anim), current_time))
        elif anim == "highlight_sweep" and not is_short:
            sfx_list.append((generate_sfx("whoosh", duration=0.4, amplitude=amp_anim), current_time))

        trans_time = float(event.get("transition_at", current_time + seg_dur))
        if trans in ("glitch", "flash"):
            sfx_list.append((generate_sfx("whoosh", duration=0.5, amplitude=amp_trans), trans_time - 0.2))
        elif trans == "swipe":
            sfx_list.append((generate_sfx("swoosh", duration=0.4, amplitude=amp_anim), max(0.0, trans_time - 0.1)))
        elif trans == "zoom" and not is_short:
            sfx_list.append((generate_sfx("bass_drop", duration=0.6, amplitude=amp_anim), max(0.0, trans_time - 0.1)))
    return sfx_list


def _finalize_muxed_output(video_only_path: str, audio_path: str, output_path: str) -> None:
    """Mux audio, validate final MP4, then remove intermediates."""
    add_audio_to_video(video_only_path, audio_path, output_path)
    if not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
        raise RuntimeError(f"Final MP4 missing after mux: {output_path}")
    if os.path.exists(video_only_path):
        os.remove(video_only_path)
    if os.path.exists(audio_path):
        os.remove(audio_path)


def _load_voiceover_array(
    script: dict,
    output_path: str,
    provider: str,
    voice: str | None,
    render_warnings=None,
    audio_driven: bool = True,
    product_name: str = "",
):
    """Generate TTS for script segments and return a float32 numpy array, or None.

    When audio_driven=True, mutates script segment durations to measured TTS + pause
    so the visual timeline can share the same clock.
    """
    try:
        vo_dir = os.path.dirname(output_path) or "."
        vo_path, _timing = generate_voiceover_for_script(
            script,
            vo_dir,
            provider=provider,
            voice=voice,
            audio_driven=audio_driven,
            product_name=product_name or "",
        )
        if not vo_path or not os.path.exists(vo_path):
            if render_warnings is not None:
                render_warnings.append("TTS voiceover file was not produced")
            return None
        rate, data = read_wav(vo_path) if vo_path.endswith(".wav") else (None, None)
        if data is None:
            # mp3 / other: decode via moviepy AudioFileClip → resample to AUDIO_SAMPLE_RATE
            clip = AudioFileClip(vo_path)
            arr = clip.to_soundarray(fps=AUDIO_SAMPLE_RATE)
            clip.close()
            if arr.ndim > 1:
                arr = arr.mean(axis=1)
            return arr.astype(np.float64)
        if data.dtype == np.int16:
            arr = data.astype(np.float64) / 32767.0
        else:
            arr = data.astype(np.float64)
        if arr.ndim > 1:
            arr = arr.mean(axis=1)
        if rate and rate != AUDIO_SAMPLE_RATE and len(arr) > 0:
            duration = len(arr) / float(rate)
            target_len = int(duration * AUDIO_SAMPLE_RATE)
            x_old = np.linspace(0, 1, len(arr), endpoint=False)
            x_new = np.linspace(0, 1, target_len, endpoint=False)
            arr = np.interp(x_new, x_old, arr)
        return arr
    except Exception as e:
        print(f"Warning: TTS voiceover failed ({e})")
        if render_warnings is not None:
            render_warnings.append(f"TTS voiceover failed: {e}")
        return None


def _prepare_tts_before_render(
    script: dict,
    output_path: str,
    use_tts: bool,
    tts_provider: str,
    tts_voice: str | None,
    render_warnings: list | None,
    product_name: str = "",
):
    """Run TTS first so segment durations drive the visual timeline."""
    if not use_tts:
        return None
    voiceover_array = _load_voiceover_array(
        script,
        output_path,
        tts_provider,
        tts_voice,
        render_warnings,
        audio_driven=True,
        product_name=product_name or "",
    )
    if voiceover_array is None and render_warnings is not None:
        render_warnings.append("Video rendered without TTS voiceover")
    return voiceover_array


# Animation types that use kinetic effects instead of simple fades
KINETIC_ANIMATIONS = {
    "word_by_word", "typewriter", "impact_scale", "highlight_sweep",
    "shake", "slide_up", "slide_left",
}

# Transition types that use real transitions instead of crossfades
REAL_TRANSITIONS = {"glitch", "flash", "swipe", "zoom", "cut"}



# BEGIN UNLOVED_LONG_FORM_FONT_SCALE_HELPER
import os as _unloved_os

@contextmanager
def _unloved_scaled_long_form_fonts():
    """
    Scale down fonts only while rendering long-form videos.

    This fixes long-form text overlays that are too large or slightly out of frame
    without changing short-form rendering.
    """
    try:
        from PIL import ImageFont as _PILImageFont
    except Exception:
        yield
        return

    original_truetype = getattr(_PILImageFont, "truetype", None)
    if original_truetype is None:
        yield
        return

    try:
        scale = float(_unloved_os.getenv("SHADOWCAST_LONG_FORM_FONT_SCALE", "0.62"))
    except Exception:
        scale = 0.62

    # Keep this conservative so tiny captions do not become unreadable.
    minimum_size = int(_unloved_os.getenv("SHADOWCAST_LONG_FORM_MIN_FONT_SIZE", "18"))

    def scaled_truetype(font, size=None, *args, **kwargs):
        if size is None:
            return original_truetype(font, size, *args, **kwargs)

        try:
            scaled_size = max(minimum_size, int(float(size) * scale))
        except Exception:
            scaled_size = size

        return original_truetype(font, scaled_size, *args, **kwargs)

    _PILImageFont.truetype = scaled_truetype
    try:
        yield
    finally:
        _PILImageFont.truetype = original_truetype
# END UNLOVED_LONG_FORM_FONT_SCALE_HELPER
def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return (255, 255, 255)


def ensure_readable_color(text_rgb: tuple, bg_rgb: tuple) -> tuple:
    """Ensure text color has enough contrast against background."""
    def luminance(rgb):
        vals = [c / 255.0 for c in rgb]
        vals = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in vals]
        return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]
    
    l_text = luminance(text_rgb)
    l_bg = luminance(bg_rgb)
    
    lighter = max(l_text, l_bg)
    darker = min(l_text, l_bg)
    ratio = (lighter + 0.05) / (darker + 0.05)
    
    if ratio < 3.0:
        boosted = tuple(min(255, c + 120) for c in text_rgb)
        return boosted
    return text_rgb


def create_gradient_bg(width: int, height: int, color1: tuple, color2: tuple) -> np.ndarray:
    """Create a vertical gradient background."""
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        ratio = y / height
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        arr[y, :] = [r, g, b]
    return arr


def create_radial_gradient_bg(width: int, height: int, center_color: tuple, edge_color: tuple) -> np.ndarray:
    """Create a radial gradient background."""
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    cx, cy = width // 2, height // 2
    max_dist = math.sqrt(cx**2 + cy**2)
    
    y_coords, x_coords = np.mgrid[0:height, 0:width]
    dist = np.sqrt((x_coords - cx)**2 + (y_coords - cy)**2)
    ratio = np.clip(dist / max_dist, 0, 1)
    
    for c in range(3):
        arr[:, :, c] = (center_color[c] * (1 - ratio) + edge_color[c] * ratio).astype(np.uint8)
    
    return arr


def create_particle_overlay(width: int, height: int, color: tuple, num_particles: int = 15, rng: random.Random | None = None) -> Image.Image:
    """Create a subtle particle/bokeh overlay."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    rnd = rng or random

    for _ in range(num_particles):
        x = rnd.randint(0, width)
        y = rnd.randint(0, height)
        size = rnd.randint(2, 15)
        alpha = rnd.randint(15, 60)
        draw.ellipse(
            [x - size, y - size, x + size, y + size],
            fill=(*color, alpha),
        )
    
    img = img.filter(ImageFilter.GaussianBlur(radius=2))
    return img


def render_text_frame(
    text: str,
    width: int,
    height: int,
    text_color: tuple = (255, 255, 255),
    bg_color: tuple = None,
    text_style: str = "headline_bold",
    is_short_form: bool = False,
    accent_color: tuple = None,
    add_glow: bool = True,
    content_style: str = "honest_review",
    bg_seed: int | None = None,
):
    """Render a single text frame with professional styling using PIL."""
    text_style = normalize_text_style(text_style)
    
    # Use brand palette
    if bg_color is None:
        bg_color = BRAND_BG
    if accent_color is None:
        accent_color = BRAND_ACCENT
    
    # Create dynamic background using bg_generator
    try:
        from bg_generator import generate_background, apply_vignette, get_style_for_content
        bg_style = get_style_for_content(normalize_content_style(content_style), hook_type="")
        bg_img = generate_background(
            width, height, style=bg_style, accent_color=accent_color, seed=bg_seed
        )
        # Bug 2 fix: enforce dark theme — if generated background is too bright, fall back to near-black
        bg_arr_check = np.array(bg_img)
        avg_luminance = float(np.mean(bg_arr_check))
        if avg_luminance > 50:
            bg_img = Image.new("RGB", (width, height), BRAND_BG)
        bg_img = apply_vignette(bg_img, strength=0.3)
        bg_img = bg_img.convert("RGBA")
    except Exception:
        # Fallback to original gradient
        rnd = random.Random(bg_seed) if bg_seed is not None else random
        bg_variant = rnd.choice(["vertical", "radial"])
        darker = tuple(max(0, c - 10) for c in bg_color)
        if bg_variant == "vertical":
            bg_arr = create_gradient_bg(width, height, bg_color, darker)
        else:
            lighter_center = tuple(min(255, c + 20) for c in bg_color)
            bg_arr = create_radial_gradient_bg(width, height, lighter_center, bg_color)
        bg_img = Image.fromarray(bg_arr, "RGB").convert("RGBA")
    
    # Add particle overlay
    particle_rng = random.Random((bg_seed or 0) + 17) if bg_seed is not None else None
    particles = create_particle_overlay(
        width, height, accent_color, num_particles=12, rng=particle_rng
    )
    bg_img = Image.alpha_composite(bg_img, particles)
    
    # Get font info
    font_path, size_mult = STYLE_FONT_MAP.get(text_style, (FONT_BOLD, 1.0))
    
    base_font_size = int(width * 0.055) if is_short_form else int(width * 0.04)
    font_size = int(base_font_size * size_mult)
    font_size = max(24, min(font_size, 160))
    
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.truetype(FONT_BOLD, font_size)
    
    draw = ImageDraw.Draw(bg_img)
    
    # Word wrap
    max_chars = 25 if is_short_form else 35
    if text_style == "stat_number":
        max_chars = 15
    wrapped = textwrap.fill(text, width=max_chars)
    
    # Calculate text position (centered)
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center")
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (width - text_w) // 2
    y = (height - text_h) // 2
    
    # Draw text glow/shadow
    if add_glow:
        glow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)
        glow_color = (*accent_color, 60)
        for offset in [2, 1]:
            glow_draw.multiline_text(
                (x + offset, y + offset), wrapped, font=font,
                fill=glow_color, align="center"
            )
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=4))
        bg_img = Image.alpha_composite(bg_img, glow_layer)
        draw = ImageDraw.Draw(bg_img)
    
    # Draw text outline/stroke
    stroke_color = (0, 0, 0, 200)
    for dx, dy in [(-2,0),(2,0),(0,-2),(0,2),(-1,-1),(1,1),(-1,1),(1,-1)]:
        draw.multiline_text(
            (x + dx, y + dy), wrapped, font=font,
            fill=stroke_color, align="center"
        )
    
    # Draw main text
    draw.multiline_text(
        (x, y), wrapped, font=font,
        fill=(*text_color, 255), align="center"
    )
    
    # Add accent bar for CTA style
    if text_style == "cta_button":
        bar_y = y + text_h + 20
        bar_w = min(text_w + 40, width - 80)
        bar_x = (width - bar_w) // 2
        draw.rounded_rectangle(
            [bar_x, bar_y, bar_x + bar_w, bar_y + 8],
            radius=4,
            fill=(*accent_color, 200),
        )
    
    # Add decorative lines for verdict
    if text_style == "verdict":
        line_y = y - 20
        draw.line([(width // 4, line_y), (3 * width // 4, line_y)], fill=(*accent_color, 150), width=3)
        line_y2 = y + text_h + 20
        draw.line([(width // 4, line_y2), (3 * width // 4, line_y2)], fill=(*accent_color, 150), width=3)
    
    # Add pros/cons indicators
    if text_style == "pros":
        indicator_size = font_size // 2
        draw.text((x - indicator_size - 10, y), "✓", font=font, fill=(0, 255, 100, 255))
    elif text_style == "cons":
        indicator_size = font_size // 2
        draw.text((x - indicator_size - 10, y), "✗", font=font, fill=(255, 80, 80, 255))
    elif text_style == "elimination":
        indicator_size = font_size // 2
        draw.text((x - indicator_size - 10, y), "✗", font=font, fill=(255, 60, 60, 255))
        strike_y = y + text_h // 2
        draw.line([(x - 8, strike_y), (x + text_w + 8, strike_y)], fill=(255, 60, 60, 200), width=3)
    
    # Convert to RGB numpy array
    result = bg_img.convert("RGB")
    return np.array(result)


def build_segment_clip(
    seg,
    width,
    height,
    is_short_form,
    accent_color,
    base_bg,
    content_style="honest_review",
    bg_seed: int | None = None,
    product_image_path: str | None = None,
    segment_index: int = 0,
):
    """Build a clip for a single segment and return (clip, terminal_frame)."""
    text = seg.get("text", "")
    duration = seg.get("duration", 2.5 if is_short_form else 4.0)
    text_style = normalize_text_style(seg.get("text_style", "headline_bold"))
    animation = seg.get("animation", "fade_in")
    is_interrupt = seg.get("is_pattern_interrupt", False)
    use_hero = bool(product_image_path) and segment_wants_product_hero(
        seg, segment_index=segment_index
    )

    def _maybe_hero(frame):
        if not use_hero:
            return frame
        return frame_with_product_hero(
            frame, product_image_path, is_short_form=is_short_form
        )

    # Parse colors
    try:
        text_color = hex_to_rgb(seg.get("text_color", "#FFFFFF"))
    except Exception:
        text_color = (255, 255, 255)
    
    try:
        bg_color = hex_to_rgb(seg.get("bg_color", ""))
    except Exception:
        bg_color = base_bg
    
    text_color = ensure_readable_color(text_color, bg_color)
    
    if is_interrupt:
        text_color = accent_color
        text_style = "accent_pop"
    
    # ── Comparison layout path (for VS Battle segments) ──
    layout = seg.get("layout", None)
    if layout == "vs_split":
        product_a = seg.get("product_a", "Product A")
        product_b = seg.get("product_b", "Product B")
        frame = _maybe_hero(render_vs_split_screen(width, height, product_a, product_b, accent_color))
        clip = ImageClip(frame, duration=duration)
        clip = clip.with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.2)])
        return clip, frame
    elif layout == "spec_compare":
        spec_name = seg.get("spec_name", text)
        value_a = seg.get("value_a", "")
        value_b = seg.get("value_b", "")
        winner = seg.get("winner", "a")
        frame = _maybe_hero(render_spec_comparison(width, height, spec_name, value_a, value_b, winner, accent_color))
        clip = ImageClip(frame, duration=duration)
        clip = clip.with_effects([vfx.FadeIn(0.2), vfx.FadeOut(0.2)])
        return clip, frame
    elif layout == "scorecard":
        product_a = seg.get("product_a", "Product A")
        product_b = seg.get("product_b", "Product B")
        scores = seg.get("scores", [])
        frame = _maybe_hero(render_scorecard(width, height, product_a, product_b, scores, accent_color))
        clip = ImageClip(frame, duration=duration)
        clip = clip.with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.3)])
        return clip, frame
    elif layout == "price_compare":
        products = seg.get("price_products", [])
        frame = _maybe_hero(render_price_comparison(width, height, products, accent_color))
        clip = ImageClip(frame, duration=duration)
        clip = clip.with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.2)])
        return clip, frame
    elif layout == "winner_reveal":
        winner_name = seg.get("winner_name", text)
        frame = _maybe_hero(render_winner_reveal(width, height, winner_name, accent_color))
        clip = ImageClip(frame, duration=duration)
        clip = clip.with_effects([vfx.FadeIn(0.4), vfx.FadeOut(0.3)])
        return clip, frame

    static_frame = render_text_frame(
        text=text, width=width, height=height,
        text_color=text_color, bg_color=bg_color,
        text_style=text_style, is_short_form=is_short_form,
        accent_color=accent_color, add_glow=is_interrupt,
        content_style=content_style,
        bg_seed=bg_seed,
    )
    static_frame = _maybe_hero(static_frame)

    # Hero stills use the static path so the product image stays visible.
    if use_hero:
        animation = "fade_in"
    
    # ── Kinetic typography path ──
    if animation == "word_by_word":
        clip = create_word_by_word_clip(
            text, width, height, duration, text_color, bg_color,
            accent_color, FONT_BOLD, is_short_form
        )
        return clip, _terminal_frame_from_clip(clip, width, height, static_frame)
    
    elif animation == "typewriter":
        clip = create_typewriter_clip(
            text, width, height, duration, text_color, bg_color,
            accent_color, FONT_BOLD, is_short_form
        )
        return clip, _terminal_frame_from_clip(clip, width, height, static_frame)
    
    elif animation == "impact_scale" or (text_style in ("stat_number", "accent_pop") and animation in ("pop_in", "zoom_in")):
        clip = create_impact_scale_clip(
            text, width, height, duration, text_color, bg_color,
            accent_color, FONT_BOLD, is_short_form
        )
        return clip, _terminal_frame_from_clip(clip, width, height, static_frame)
    
    elif animation == "highlight_sweep":
        clip = create_highlight_sweep_clip(
            text, width, height, duration, text_color, bg_color,
            accent_color, FONT_BOLD, is_short_form
        )
        return clip, _terminal_frame_from_clip(clip, width, height, static_frame)
    
    else:
        # ── Standard frame path (with improved animations) ──
        frame = static_frame
        
        if animation == "shake":
            clip = create_shake_clip(frame, duration, intensity=5)
        elif animation == "slide_up":
            clip = create_slide_up_clip(frame, width, height, duration)
        elif animation == "slide_left":
            clip = create_slide_left_clip(frame, width, height, duration)
        else:
            # Standard fade/zoom/pop
            clip = ImageClip(frame, duration=duration)
            if animation == "zoom_in":
                def zoom_effect(get_frame, t):
                    progress = min(1.0, t / 0.3)
                    scale = 1.2 - 0.2 * progress
                    fr = get_frame(t)
                    h, w = fr.shape[:2]
                    new_h, new_w = int(h * scale), int(w * scale)
                    img = Image.fromarray(fr)
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                    left = (new_w - w) // 2
                    top = (new_h - h) // 2
                    img = img.crop((left, top, left + w, top + h))
                    return np.array(img)
                clip = clip.transform(zoom_effect)
            elif animation == "pop_in":
                clip = clip.with_effects([vfx.FadeIn(min(0.15, duration * 0.15))])
            else:
                clip = clip.with_effects([vfx.FadeIn(min(0.3, duration * 0.3))])
        
        # Add fade out
        clip = clip.with_effects([vfx.FadeOut(min(0.15, duration * 0.15))])
        return clip, frame


def build_transition_clip(frame_a, frame_b, transition_type, accent_color):
    """Build a transition clip between two frames."""
    if transition_type == "glitch":
        return create_glitch_transition(frame_a, frame_b, duration=0.15)
    elif transition_type == "flash":
        return create_flash_transition(frame_a, frame_b, accent_color, duration=0.1)
    elif transition_type == "swipe":
        return create_swipe_transition(frame_a, frame_b, duration=0.3)
    elif transition_type == "zoom":
        return create_zoom_transition(frame_a, frame_b, duration=0.2)
    else:
        # "cut" or "fade" — no transition clip needed
        return None


def composite_overlays(base_clip, overlays_rgba, width, height, duration):
    """Composite RGBA PIL overlay images onto a base clip."""
    overlay_clips = []
    for overlay_img in overlays_rgba:
        # Convert RGBA PIL Image to numpy array
        overlay_arr = np.array(overlay_img.convert("RGBA"))
        overlay_clip = ImageClip(overlay_arr, duration=duration)
        overlay_clips.append(overlay_clip)
    
    if overlay_clips:
        return CompositeVideoClip([base_clip] + overlay_clips)
    return base_clip


def render_short_form_video(
    script: dict,
    output_path: str,
    use_tts: bool = False,
    product_name: str = "",
    price: str = "",
    series_name: str = "",
    content_style: str = "honest_review",
    competitors=None,
    audio_enabled: bool = True,
    audio_mood: str | None = None,
    tts_provider: str = "auto",
    tts_voice: str | None = None,
    video_preset: str | None = None,
    render_warnings: list | None = None,
    render_seed: int | None = None,
    product_image_path: str | None = None,
) -> str:
    """Render a short-form (YouTube Shorts) video from script JSON."""
    if competitors is None:
        competitors = []
    content_style = normalize_content_style(content_style)
    render_preset = resolve_video_preset(video_preset)
    if render_seed is None:
        fp = compute_render_fingerprint(
            script,
            fmt=SHORT_FORM,
            render_options={
                "content_style": content_style,
                "audio_enabled": audio_enabled,
                "audio_mood": audio_mood,
                "use_tts": use_tts,
                "tts_provider": tts_provider,
                "tts_voice": tts_voice,
                "video_preset": render_preset,
                "product_name": product_name,
                "price": price,
                "series_name": series_name,
            },
        )
        render_seed = fingerprint_seed(fp)

    with _seeded_render_rng(render_seed):
        return _render_short_form_video_impl(
            script=script,
            output_path=output_path,
            use_tts=use_tts,
            product_name=product_name,
            price=price,
            series_name=series_name,
            content_style=content_style,
            audio_enabled=audio_enabled,
            audio_mood=audio_mood,
            tts_provider=tts_provider,
            tts_voice=tts_voice,
            render_preset=render_preset,
            render_warnings=render_warnings,
            render_seed=render_seed,
            product_image_path=product_image_path,
        )


def _render_short_form_video_impl(
    *,
    script: dict,
    output_path: str,
    use_tts: bool,
    product_name: str,
    price: str,
    series_name: str,
    content_style: str,
    audio_enabled: bool,
    audio_mood: str | None,
    tts_provider: str,
    tts_voice: str | None,
    render_preset: str,
    render_warnings: list | None,
    render_seed: int,
    product_image_path: str | None = None,
) -> str:
    WIDTH, HEIGHT = 1080, 1920  # 9:16 vertical
    FPS = 30

    segments = script.get("segments", [])
    if not segments:
        raise ValueError("No segments found in script")

    # TTS-first: measure speech and rewrite segment durations before timeline/clips.
    voiceover_array = _prepare_tts_before_render(
        script,
        output_path,
        use_tts,
        tts_provider,
        tts_voice,
        render_warnings,
        product_name=product_name or "",
    )

    accent_color = BRAND_ACCENT
    base_bg = BRAND_BG
    timeline = build_render_timeline(script, SHORT_FORM)
    intro_seconds = float(timeline["intro_seconds"])
    total_segments = len(segments)

    clips = []

    # ── Branded Intro (2 seconds) ──
    intro_frame = render_branded_intro(WIDTH, HEIGHT, series_name, product_name)
    intro_clip = ImageClip(intro_frame, duration=intro_seconds)
    intro_clip = intro_clip.with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.3)])
    clips.append(intro_clip)

    # ── Content Segments (frame generated once, reused for transitions) ──
    rendered_frames = []
    segment_clips = []

    for i, seg in enumerate(segments):
        clip, frame = build_segment_clip(
            seg, WIDTH, HEIGHT, True, accent_color, base_bg, content_style,
            bg_seed=render_seed + i + 1,
            product_image_path=product_image_path,
            segment_index=i,
        )
        segment_clips.append(clip)
        rendered_frames.append(frame)

    # Interleave segments with transitions
    for i, seg_clip in enumerate(segment_clips):
        clips.append(seg_clip)

        if i < len(segment_clips) - 1:
            transition_type = segments[i].get("transition_to_next", "fade")
            if transition_type in REAL_TRANSITIONS and transition_type != "cut":
                trans_clip = build_transition_clip(
                    rendered_frames[i], rendered_frames[i + 1],
                    transition_type, accent_color
                )
                if trans_clip is not None:
                    clips.append(trans_clip)

    # ── Engagement: Subscribe card before outro (short form) ──
    if total_segments > 5:
        sub_frame = render_subscribe_card(WIDTH, HEIGHT, accent_color)
        sub_clip = ImageClip(sub_frame, duration=2.0)
        sub_clip = sub_clip.with_effects([vfx.FadeIn(0.2), vfx.FadeOut(0.2)])
        clips.append(sub_clip)

    # ── Branded Outro (2 seconds) ──
    outro_frame = render_branded_outro(WIDTH, HEIGHT)
    outro_clip = ImageClip(outro_frame, duration=2.0)
    outro_clip = outro_clip.with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.3)])
    clips.append(outro_clip)

    # Concatenate all clips
    final = concatenate_videoclips(clips, method="compose")

    # ── Overlays: watermark + entity-timed lower third + Shorts captions ──
    overlay_layers = [final]

    watermark = render_watermark_overlay(WIDTH, HEIGHT)
    watermark_arr = np.array(watermark.convert("RGBA"))
    watermark_clip = ImageClip(watermark_arr, duration=final.duration)
    overlay_layers.append(watermark_clip)

    timing_rows: list = []
    vo_hint = ""
    if use_tts:
        vo_hint = os.path.join(
            os.path.dirname(output_path) or ".",
            f"{script.get('hook_type', 'unknown')}_short_form_voiceover.mp3",
        )
        timing_rows = resolve_tts_timing(script, vo_hint)

    # Entity lower-third: first product mention on shared TTS clock (4–7s hold).
    # Shorts bar sits above bottom UI; captions stay mid-upper — no Y overlap.
    if product_name:
        lower_third = render_lower_third(WIDTH, HEIGHT, product_name, price, is_short_form=True)
        lt_arr = np.array(lower_third.convert("RGBA"))
        lt_ev = lower_third_event_from_timing(
            timing_rows,
            product_name,
            intro_offset=intro_seconds,
            video_duration=float(final.duration),
        )
        if lt_ev:
            lt_start = float(lt_ev["start"])
            lt_dur = float(lt_ev["duration"])
            lt_clip = ImageClip(lt_arr, duration=lt_dur).with_start(lt_start)
            if lt_dur >= 0.4:
                fade = min(0.25, lt_dur / 4.0)
                lt_clip = lt_clip.with_effects([vfx.FadeIn(fade), vfx.FadeOut(fade)])
            overlay_layers.append(lt_clip)

    # Burn-in Shorts captions synced to shared TTS timing clock (speech window).
    # Karaoke: WhisperX forced-align when SHADOWCAST_WHISPERX_ALIGN=1, else proportional.
    if use_tts and timing_rows:
        chunk_events = caption_events_from_timing(timing_rows, intro_offset=intro_seconds)
        caption_events = None
        if whisperx_align_enabled() and vo_hint and os.path.isfile(vo_hint):
            transcript = " ".join(
                str(r.get("text") or "").strip() for r in timing_rows if r.get("text")
            )
            word_timings = align_words_to_audio(vo_hint, transcript)
            if word_timings:
                # VO file is speech-only; add intro chrome so highlights match muxed timeline.
                caption_events = refine_caption_events_with_word_align(
                    chunk_events,
                    word_timings,
                    intro_offset=intro_seconds,
                )
        if caption_events is None:
            caption_events = expand_caption_word_highlights(
                chunk_events, enabled=shorts_word_highlight_enabled()
            )
        for ev in caption_events:
            start = float(ev["start"])
            if start >= float(final.duration):
                continue
            dur = min(float(ev["duration"]), max(0.1, float(final.duration) - start))
            cap_img = render_shorts_caption(
                WIDTH, HEIGHT, ev["text"], highlight_index=ev.get("highlight_index")
            )
            cap_clip = ImageClip(np.array(cap_img.convert("RGBA")), duration=dur).with_start(start)
            if dur >= 0.25:
                fade = min(0.08, dur / 3.0)
                cap_clip = cap_clip.with_effects([vfx.FadeIn(fade), vfx.FadeOut(fade)])
            overlay_layers.append(cap_clip)

    final_with_overlays = CompositeVideoClip(overlay_layers)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    video_only_path = output_path.replace(".mp4", "_video_only.mp4")

    try:
        encode_kwargs = resolve_write_videofile_kwargs(render_preset)
        final_with_overlays.write_videofile(
            video_only_path,
            fps=FPS,
            audio=False,
            logger=None,
            **encode_kwargs,
        )

        if not audio_enabled and not use_tts:
            if os.path.exists(video_only_path):
                os.rename(video_only_path, output_path)
        else:
            try:
                video_duration = final.duration
                mood = resolve_audio_mood(audio_mood, content_style, "short_form")
                tempo = MOOD_TEMPO.get(mood, 100)

                if audio_enabled:
                    bg_music = generate_background_music(
                        video_duration,
                        mood=mood,
                        tempo=tempo,
                    )
                    sfx_list = _schedule_sfx_from_timeline(timeline, is_short=True)
                else:
                    bg_music = np.zeros(int(video_duration * AUDIO_SAMPLE_RATE))
                    sfx_list = []

                audio_path = output_path.replace(".mp4", "_audio.wav")
                mix_audio(
                    bg_music,
                    sfx_list,
                    voiceover_array=voiceover_array,
                    output_path=audio_path,
                    voiceover_start_seconds=intro_seconds,
                )
                _finalize_muxed_output(video_only_path, audio_path, output_path)
            except Exception as e:
                print(f"Warning: Audio generation failed ({e}), preserving video-only output")
                if render_warnings is not None:
                    render_warnings.append(f"Audio generation failed, using silent video: {e}")
                if os.path.exists(video_only_path) and not os.path.exists(output_path):
                    os.rename(video_only_path, output_path)
    finally:
        pass

    # Cleanup
    final_with_overlays.close()
    final.close()
    for c in clips:
        try:
            c.close()
        except Exception:
            pass

    if use_tts and timing_rows and os.path.exists(output_path):
        write_srt_sidecar(output_path, timing_rows, intro_offset=intro_seconds)

    return output_path


def render_long_form_video(
    script: dict,
    output_path: str,
    use_tts: bool = False,
    product_name: str = "",
    price: str = "",
    series_name: str = "",
    content_style: str = "honest_review",
    competitors=None,
    audio_enabled: bool = True,
    audio_mood: str | None = None,
    tts_provider: str = "auto",
    tts_voice: str | None = None,
    video_preset: str | None = None,
    render_warnings: list | None = None,
    render_seed: int | None = None,
    product_image_path: str | None = None,
) -> str:
    if competitors is None:
        competitors = []
    content_style = normalize_content_style(content_style)
    render_preset = resolve_video_preset(video_preset)
    if render_seed is None:
        fp = compute_render_fingerprint(
            script,
            fmt=LONG_FORM,
            render_options={
                "content_style": content_style,
                "audio_enabled": audio_enabled,
                "audio_mood": audio_mood,
                "use_tts": use_tts,
                "tts_provider": tts_provider,
                "tts_voice": tts_voice,
                "video_preset": render_preset,
                "product_name": product_name,
                "price": price,
                "series_name": series_name,
            },
        )
        render_seed = fingerprint_seed(fp)

    with _seeded_render_rng(render_seed):
        with _unloved_scaled_long_form_fonts():
            return _render_long_form_video_impl(
                script=script,
                output_path=output_path,
                use_tts=use_tts,
                product_name=product_name,
                price=price,
                series_name=series_name,
                content_style=content_style,
                audio_enabled=audio_enabled,
                audio_mood=audio_mood,
                tts_provider=tts_provider,
                tts_voice=tts_voice,
                render_preset=render_preset,
                render_warnings=render_warnings,
                render_seed=render_seed,
                product_image_path=product_image_path,
            )


def _render_long_form_video_impl(
    *,
    script: dict,
    output_path: str,
    use_tts: bool,
    product_name: str,
    price: str,
    series_name: str,
    content_style: str,
    audio_enabled: bool,
    audio_mood: str | None,
    tts_provider: str,
    tts_voice: str | None,
    render_preset: str,
    render_warnings: list | None,
    render_seed: int,
    product_image_path: str | None = None,
) -> str:
    WIDTH, HEIGHT = 1920, 1080  # 16:9 landscape
    FPS = 30

    chapters = script.get("chapters", [])
    if not chapters:
        raise ValueError("No chapters found in script")

    # TTS-first: measure speech and rewrite segment durations before timeline/clips.
    voiceover_array = _prepare_tts_before_render(
        script,
        output_path,
        use_tts,
        tts_provider,
        tts_voice,
        render_warnings,
        product_name=product_name or "",
    )

    accent_color = BRAND_ACCENT
    base_bg = BRAND_BG
    timeline = build_render_timeline(script, LONG_FORM)
    intro_seconds = float(timeline["intro_seconds"])
    total_chapters = len(chapters)

    all_clips = []

    # ── Branded Intro (3 seconds for long form) ──
    intro_frame = render_branded_intro(WIDTH, HEIGHT, series_name, product_name)
    intro_clip = ImageClip(intro_frame, duration=intro_seconds)
    intro_clip = intro_clip.with_effects([vfx.FadeIn(0.5), vfx.FadeOut(0.5)])
    all_clips.append(intro_clip)

    segment_counter = 0
    engagement_inserted = False

    for ch_idx, chapter in enumerate(chapters):
        chapter_name = chapter.get("chapter_name", "")
        segments = chapter.get("segments", [])

        section_type = None
        ch_lower = chapter_name.lower()
        if any(w in ch_lower for w in ["pro", "good", "strength", "advantage"]):
            section_type = "pros"
        elif any(w in ch_lower for w in ["con", "bad", "weakness", "drawback"]):
            section_type = "cons"
        elif any(w in ch_lower for w in ["verdict", "final", "conclusion", "rating"]):
            section_type = "verdict"
        elif any(w in ch_lower for w in ["vs", "compar", "battle", "versus"]):
            section_type = "comparison"

        chapter_frame = render_text_frame(
            text=chapter_name.upper(),
            width=WIDTH, height=HEIGHT,
            text_color=accent_color,
            bg_color=base_bg,
            text_style="headline_bold",
            is_short_form=False,
            accent_color=accent_color,
            content_style=content_style,
            bg_seed=render_seed + 1000 + ch_idx,
        )

        if section_type:
            header_overlay = render_section_header(WIDTH, HEIGHT, section_type, accent_color)
            chapter_pil = Image.fromarray(chapter_frame).convert("RGBA")
            chapter_pil = Image.alpha_composite(chapter_pil, header_overlay)
            chapter_frame = np.array(chapter_pil.convert("RGB"))

        chapter_clip = ImageClip(chapter_frame, duration=2.5)
        chapter_clip = chapter_clip.with_effects([vfx.FadeIn(0.4), vfx.FadeOut(0.4)])
        all_clips.append(chapter_clip)

        # Optional stock B-roll pad between chapter title and first segment.
        broll_clip = make_broll_clip(
            section_type,
            duration=2.0,
            width=WIDTH,
            height=HEIGHT,
        )
        if broll_clip is not None:
            all_clips.append(broll_clip)

        rendered_frames = []
        segment_clips_ch = []

        for seg in segments:
            clip, frame = build_segment_clip(
                seg, WIDTH, HEIGHT, False, accent_color, base_bg, content_style,
                bg_seed=render_seed + 2000 + segment_counter,
                product_image_path=product_image_path,
                segment_index=segment_counter,
            )
            segment_clips_ch.append(clip)
            rendered_frames.append(frame)
            segment_counter += 1

        for i, seg_clip in enumerate(segment_clips_ch):
            all_clips.append(seg_clip)

            if i < len(segment_clips_ch) - 1:
                transition_type = segments[i].get("transition_to_next", "fade")
                if transition_type in REAL_TRANSITIONS and transition_type != "cut":
                    trans_clip = build_transition_clip(
                        rendered_frames[i], rendered_frames[i + 1],
                        transition_type, accent_color
                    )
                    if trans_clip is not None:
                        all_clips.append(trans_clip)

        if not engagement_inserted and ch_idx >= total_chapters // 2:
            comment_frame = render_comment_prompt(
                WIDTH, HEIGHT,
                "What do you think? Drop your opinion below!",
                accent_color
            )
            comment_clip = ImageClip(comment_frame, duration=3.0)
            comment_clip = comment_clip.with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.3)])
            all_clips.append(comment_clip)
            engagement_inserted = True

    # ── Subscribe card before outro ──
    sub_frame = render_subscribe_card(WIDTH, HEIGHT, accent_color)
    sub_clip = ImageClip(sub_frame, duration=3.0)
    sub_clip = sub_clip.with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.3)])
    all_clips.append(sub_clip)

    # ── Branded Outro (3 seconds) ──
    outro_frame = render_branded_outro(WIDTH, HEIGHT)
    outro_clip = ImageClip(outro_frame, duration=3.0)
    outro_clip = outro_clip.with_effects([vfx.FadeIn(0.5), vfx.FadeOut(0.5)])
    all_clips.append(outro_clip)

    final = concatenate_videoclips(all_clips, method="compose")

    overlay_layers = [final]

    watermark = render_watermark_overlay(WIDTH, HEIGHT)
    watermark_arr = np.array(watermark.convert("RGBA"))
    watermark_clip = ImageClip(watermark_arr, duration=final.duration)
    overlay_layers.append(watermark_clip)

    timing_rows: list = []
    if use_tts:
        vo_hint = os.path.join(
            os.path.dirname(output_path) or ".",
            f"{script.get('hook_type', 'unknown')}_long_form_voiceover.mp3",
        )
        timing_rows = resolve_tts_timing(script, vo_hint)

    # Entity lower-third: first product mention on shared TTS clock (4–7s hold).
    if product_name:
        lower_third = render_lower_third(WIDTH, HEIGHT, product_name, price, is_short_form=False)
        lt_arr = np.array(lower_third.convert("RGBA"))
        lt_ev = lower_third_event_from_timing(
            timing_rows,
            product_name,
            intro_offset=intro_seconds,
            video_duration=float(final.duration),
        )
        if lt_ev:
            lt_start = float(lt_ev["start"])
            lt_dur = float(lt_ev["duration"])
            lt_clip = ImageClip(lt_arr, duration=lt_dur).with_start(lt_start)
            if lt_dur >= 0.4:
                fade = min(0.25, lt_dur / 4.0)
                lt_clip = lt_clip.with_effects([vfx.FadeIn(fade), vfx.FadeOut(fade)])
            overlay_layers.append(lt_clip)

    # Burn-in long-form captions on shared TTS clock (lower band; SRT still written).
    if use_tts and timing_rows and longform_burnin_captions_enabled():
        chunk_events = caption_events_from_timing(timing_rows, intro_offset=intro_seconds)
        caption_events = expand_caption_word_highlights(
            chunk_events, enabled=shorts_word_highlight_enabled()
        )
        for ev in caption_events:
            start = float(ev["start"])
            if start >= float(final.duration):
                continue
            dur = min(float(ev["duration"]), max(0.1, float(final.duration) - start))
            cap_img = render_shorts_caption(
                WIDTH,
                HEIGHT,
                ev["text"],
                highlight_index=ev.get("highlight_index"),
                y_frac=0.72,
                max_width_frac=0.82,
                font_size_frac=0.032,
            )
            cap_clip = ImageClip(np.array(cap_img.convert("RGBA")), duration=dur).with_start(start)
            if dur >= 0.25:
                fade = min(0.08, dur / 3.0)
                cap_clip = cap_clip.with_effects([vfx.FadeIn(fade), vfx.FadeOut(fade)])
            overlay_layers.append(cap_clip)

    # Progress bar overlay (numpy slice animator — no PIL per frame)
    overlay_layers.append(
        _make_progress_animator(WIDTH, HEIGHT, final.duration, accent_color)
    )

    final_with_overlays = CompositeVideoClip(overlay_layers)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    video_only_path = output_path.replace(".mp4", "_video_only.mp4")

    try:
        encode_kwargs = resolve_write_videofile_kwargs(render_preset)
        final_with_overlays.write_videofile(
            video_only_path,
            fps=FPS,
            audio=False,
            logger=None,
            **encode_kwargs,
        )

        if not audio_enabled and not use_tts:
            if os.path.exists(video_only_path):
                os.rename(video_only_path, output_path)
        else:
            try:
                video_duration = final.duration
                mood = resolve_audio_mood(audio_mood, content_style, "long_form")
                tempo = MOOD_TEMPO.get(mood, 100)

                if audio_enabled:
                    bg_music = generate_background_music(
                        video_duration,
                        mood=mood,
                        tempo=tempo,
                    )
                    sfx_list = _schedule_sfx_from_timeline(timeline, is_short=False)
                else:
                    bg_music = np.zeros(int(video_duration * AUDIO_SAMPLE_RATE))
                    sfx_list = []

                audio_path = output_path.replace(".mp4", "_audio.wav")
                mix_audio(
                    bg_music,
                    sfx_list,
                    voiceover_array=voiceover_array,
                    output_path=audio_path,
                    voiceover_start_seconds=intro_seconds,
                )
                _finalize_muxed_output(video_only_path, audio_path, output_path)
            except Exception as e:
                print(f"Warning: Audio generation failed ({e}), preserving video-only output")
                if render_warnings is not None:
                    render_warnings.append(f"Audio generation failed, using silent video: {e}")
                if os.path.exists(video_only_path) and not os.path.exists(output_path):
                    os.rename(video_only_path, output_path)
    finally:
        pass

    final_with_overlays.close()
    final.close()
    for c in all_clips:
        try:
            c.close()
        except Exception:
            pass

    if use_tts and timing_rows and os.path.exists(output_path):
        write_srt_sidecar(output_path, timing_rows, intro_offset=intro_seconds)

    return output_path


def render_from_script_file(script_path: str, output_dir: str = None) -> dict:
    """Render videos from a saved script JSON file."""
    
    if output_dir is None:
        output_dir = OUTPUT_DIR
    
    with open(script_path, "r") as f:
        data = json.load(f)
    
    results = {}
    
    if "scripts" in data:
        for hook_type, formats in data["scripts"].items():
            results[hook_type] = {}
            
            if "short_form" in formats:
                sf_path = os.path.join(output_dir, f"{hook_type}_short_form.mp4")
                print(f"  Rendering {hook_type} short-form video...")
                render_short_form_video(formats["short_form"], sf_path)
                results[hook_type]["short_form"] = sf_path
                print(f"  ✓ Saved: {sf_path}")
            
            if "long_form" in formats:
                lf_path = os.path.join(output_dir, f"{hook_type}_long_form.mp4")
                print(f"  Rendering {hook_type} long-form video...")
                render_long_form_video(formats["long_form"], lf_path)
                results[hook_type]["long_form"] = lf_path
                print(f"  ✓ Saved: {lf_path}")
    
    return results


if __name__ == "__main__":
    # Quick test with a minimal script
    test_script = {
        "hook_type": "test",
        "format": "short_form",
        "total_duration_seconds": 10,
        "title_suggestion": "Test Video",
        "segments": [
            {
                "segment_id": 1,
                "start_time": 0,
                "duration": 3,
                "text": "THIS CHANGES EVERYTHING",
                "text_style": "headline_bold",
                "text_color": "#FFFFFF",
                "bg_color": "#0A0A0F",
                "animation": "word_by_word",
                "transition_to_next": "glitch",
            },
            {
                "segment_id": 2,
                "start_time": 3,
                "duration": 3,
                "text": "4.8 STARS — 12,000 Reviews",
                "text_style": "stat_number",
                "text_color": "#FFD700",
                "bg_color": "#0A0A0F",
                "animation": "impact_scale",
                "transition_to_next": "flash",
            },
            {
                "segment_id": 3,
                "start_time": 6,
                "duration": 4,
                "text": "Link in description",
                "text_style": "cta_button",
                "text_color": "#FFFFFF",
                "bg_color": "#0A0A0F",
                "animation": "slide_up",
                "transition_to_next": "fade",
            },
        ],
        "cta_text": "Check the link in description",
        "cta_placement": "end_screen",
    }
    
    out = os.path.join(OUTPUT_DIR, "test_short.mp4")
    print("Rendering test short-form video...")
    render_short_form_video(test_script, out, product_name="Test Product", price="$49.99", series_name="Worth It?")
    print(f"✓ Test video saved to {out}")
