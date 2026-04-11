"""
ShadowCast Video Renderer — v2.0
Renders script JSON into MP4 videos with kinetic typography, real transitions,
branded overlays, progress tracking, and engagement bait moments.
Supports both short-form (9:16) and long-form (16:9) formats.
"""

import json
import math
import os
import random
import textwrap
from io import BytesIO

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
)
from sound_design import (
    generate_background_music,
    generate_sfx,
    mix_audio,
    add_audio_to_video,
    SAMPLE_RATE as AUDIO_SAMPLE_RATE,
)
from scipy.io.wavfile import write as write_wav

from comparison_layouts import (
    render_vs_split_screen,
    render_spec_comparison,
    render_scorecard,
    render_price_comparison,
    render_winner_reveal,
)

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

FONT_BOLD = os.path.join(ASSETS_DIR, "Montserrat-Bold.ttf")
FONT_EXTRABOLD = os.path.join(ASSETS_DIR, "Montserrat-ExtraBold.ttf")
FONT_BLACK = os.path.join(ASSETS_DIR, "Montserrat-Black.ttf")
FONT_REGULAR = os.path.join(ASSETS_DIR, "Montserrat-Regular.ttf")

# Fallback
if not os.path.exists(FONT_BOLD):
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
    "comparison": (FONT_BOLD, 0.9),
    "verdict": (FONT_BLACK, 1.2),
}

# Animation types that use kinetic effects instead of simple fades
KINETIC_ANIMATIONS = {
    "word_by_word", "typewriter", "impact_scale", "highlight_sweep",
    "shake", "slide_up", "slide_left",
}

# Transition types that use real transitions instead of crossfades
REAL_TRANSITIONS = {"glitch", "flash", "swipe", "zoom", "cut"}


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


def create_particle_overlay(width: int, height: int, color: tuple, num_particles: int = 15) -> Image.Image:
    """Create a subtle particle/bokeh overlay."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    for _ in range(num_particles):
        x = random.randint(0, width)
        y = random.randint(0, height)
        size = random.randint(2, 15)
        alpha = random.randint(15, 60)
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
) -> np.ndarray:
    """Render a single text frame with professional styling using PIL."""
    
    # Use brand palette
    if bg_color is None:
        bg_color = BRAND_BG
    if accent_color is None:
        accent_color = BRAND_ACCENT
    
    # Create dynamic background using bg_generator
    try:
        from bg_generator import generate_background, apply_vignette, apply_film_grain, get_style_for_content
        bg_style = random.choice(["gradient", "mesh_gradient", "geometric", "bokeh", "wave", "radial", "noise", "grid", "abstract", "circuit"])
        bg_img = generate_background(width, height, style=bg_style, accent_color=accent_color)
        # Bug 2 fix: enforce dark theme — if generated background is too bright, fall back to near-black
        bg_arr_check = np.array(bg_img)
        avg_luminance = float(np.mean(bg_arr_check))
        if avg_luminance > 50:
            bg_img = Image.new("RGB", (width, height), BRAND_BG)
        bg_img = apply_vignette(bg_img, strength=0.3)
        bg_img = bg_img.convert("RGBA")
    except Exception:
        # Fallback to original gradient
        bg_variant = random.choice(["vertical", "radial"])
        darker = tuple(max(0, c - 10) for c in bg_color)
        if bg_variant == "vertical":
            bg_arr = create_gradient_bg(width, height, bg_color, darker)
        else:
            lighter_center = tuple(min(255, c + 20) for c in bg_color)
            bg_arr = create_radial_gradient_bg(width, height, lighter_center, bg_color)
        bg_img = Image.fromarray(bg_arr, "RGB").convert("RGBA")
    
    # Add particle overlay
    particles = create_particle_overlay(width, height, accent_color, num_particles=12)
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
    
    # Convert to RGB numpy array
    result = bg_img.convert("RGB")
    return np.array(result)


def build_segment_clip(seg, width, height, is_short_form, accent_color, base_bg):
    """Build a clip for a single segment, using kinetic effects when appropriate."""
    text = seg.get("text", "")
    duration = seg.get("duration", 2.5 if is_short_form else 4.0)
    text_style = seg.get("text_style", "headline_bold")
    animation = seg.get("animation", "fade_in")
    is_interrupt = seg.get("is_pattern_interrupt", False)
    
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
        frame = render_vs_split_screen(width, height, product_a, product_b, accent_color)
        clip = ImageClip(frame, duration=duration)
        clip = clip.with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.2)])
        return clip
    elif layout == "spec_compare":
        spec_name = seg.get("spec_name", text)
        value_a = seg.get("value_a", "")
        value_b = seg.get("value_b", "")
        winner = seg.get("winner", "a")
        frame = render_spec_comparison(width, height, spec_name, value_a, value_b, winner, accent_color)
        clip = ImageClip(frame, duration=duration)
        clip = clip.with_effects([vfx.FadeIn(0.2), vfx.FadeOut(0.2)])
        return clip
    elif layout == "scorecard":
        product_a = seg.get("product_a", "Product A")
        product_b = seg.get("product_b", "Product B")
        scores = seg.get("scores", [])
        frame = render_scorecard(width, height, product_a, product_b, scores, accent_color)
        clip = ImageClip(frame, duration=duration)
        clip = clip.with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.3)])
        return clip
    elif layout == "price_compare":
        products = seg.get("price_products", [])
        frame = render_price_comparison(width, height, products, accent_color)
        clip = ImageClip(frame, duration=duration)
        clip = clip.with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.2)])
        return clip
    elif layout == "winner_reveal":
        winner_name = seg.get("winner_name", text)
        frame = render_winner_reveal(width, height, winner_name, accent_color)
        clip = ImageClip(frame, duration=duration)
        clip = clip.with_effects([vfx.FadeIn(0.4), vfx.FadeOut(0.3)])
        return clip
    
    # ── Kinetic typography path ──
    if animation == "word_by_word":
        return create_word_by_word_clip(
            text, width, height, duration, text_color, bg_color,
            accent_color, FONT_BOLD, is_short_form
        )
    
    elif animation == "typewriter":
        return create_typewriter_clip(
            text, width, height, duration, text_color, bg_color,
            accent_color, FONT_BOLD, is_short_form
        )
    
    elif animation == "impact_scale" or (text_style in ("stat_number", "accent_pop") and animation in ("pop_in", "zoom_in")):
        return create_impact_scale_clip(
            text, width, height, duration, text_color, bg_color,
            accent_color, FONT_BOLD, is_short_form
        )
    
    elif animation == "highlight_sweep":
        return create_highlight_sweep_clip(
            text, width, height, duration, text_color, bg_color,
            accent_color, FONT_BOLD, is_short_form
        )
    
    else:
        # ── Standard frame path (with improved animations) ──
        frame = render_text_frame(
            text=text, width=width, height=height,
            text_color=text_color, bg_color=bg_color,
            text_style=text_style, is_short_form=is_short_form,
            accent_color=accent_color, add_glow=is_interrupt,
        )
        
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
        return clip


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
) -> str:
    """Render a short-form (YouTube Shorts) video from script JSON."""
    
    WIDTH, HEIGHT = 1080, 1920  # 9:16 vertical
    FPS = 30
    
    segments = script.get("segments", [])
    if not segments:
        raise ValueError("No segments found in script")
    
    accent_color = BRAND_ACCENT
    base_bg = BRAND_BG
    
    total_duration = script.get("total_duration_seconds", 45)
    total_segments = len(segments)
    
    clips = []
    
    # ── Branded Intro (2 seconds) ──
    intro_frame = render_branded_intro(WIDTH, HEIGHT, series_name, product_name)
    intro_clip = ImageClip(intro_frame, duration=2.0)
    intro_clip = intro_clip.with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.3)])
    clips.append(intro_clip)
    
    # ── Content Segments ──
    rendered_frames = []  # Store frames for transitions
    segment_clips = []
    
    for i, seg in enumerate(segments):
        clip = build_segment_clip(seg, WIDTH, HEIGHT, True, accent_color, base_bg)
        segment_clips.append(clip)
        
        # Render a static frame for transition purposes
        frame = render_text_frame(
            text=seg.get("text", ""),
            width=WIDTH, height=HEIGHT,
            text_color=ensure_readable_color(
                hex_to_rgb(seg.get("text_color", "#FFFFFF")) if seg.get("text_color") else (255, 255, 255),
                base_bg
            ),
            bg_color=base_bg,
            text_style=seg.get("text_style", "headline_bold"),
            is_short_form=True,
            accent_color=accent_color,
        )
        rendered_frames.append(frame)
    
    # Interleave segments with transitions
    for i, seg_clip in enumerate(segment_clips):
        clips.append(seg_clip)
        
        # Add transition between segments
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
        # Insert a subscribe reminder 2/3 through
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
    
    # ── Persistent overlays: watermark + lower third ──
    overlay_layers = [final]
    
    # Watermark
    watermark = render_watermark_overlay(WIDTH, HEIGHT)
    watermark_arr = np.array(watermark.convert("RGBA"))
    watermark_clip = ImageClip(watermark_arr, duration=final.duration)
    overlay_layers.append(watermark_clip)
    
    # Lower third (if product name provided)
    if product_name:
        lower_third = render_lower_third(WIDTH, HEIGHT, product_name, price, is_short_form=True)
        lt_arr = np.array(lower_third.convert("RGBA"))
        lt_clip = ImageClip(lt_arr, duration=final.duration)
        overlay_layers.append(lt_clip)
    
    final_with_overlays = CompositeVideoClip(overlay_layers)
    
    # Write video (without audio first)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    video_only_path = output_path.replace(".mp4", "_video_only.mp4")
    final_with_overlays.write_videofile(
        video_only_path,
        fps=FPS,
        codec="libx264",
        audio=False,
        preset="ultrafast",
        threads=4,
        logger=None,
    )
    
    # ── Generate and add audio ──
    try:
        video_duration = final.duration
        
        # Generate background music
        bg_music = generate_background_music(video_duration, mood="energetic", tempo=120)
        
        # Generate SFX timed to segment transitions
        sfx_list = []
        current_time = 2.0  # After intro
        for seg in segments:
            seg_dur = seg.get("duration", 2.5)
            anim = seg.get("animation", "fade_in")
            trans = seg.get("transition_to_next", "fade")
            
            # Text reveal SFX
            if anim in ("word_by_word", "typewriter"):
                sfx_list.append((generate_sfx("pop", duration=0.1, amplitude=0.4), current_time + 0.1))
            elif anim in ("impact_scale", "shake"):
                sfx_list.append((generate_sfx("bass_drop", duration=0.8, amplitude=0.5), current_time))
            elif anim in ("slide_up", "slide_left"):
                sfx_list.append((generate_sfx("swoosh", duration=0.4, amplitude=0.4), current_time))
            
            # Transition SFX
            trans_time = current_time + seg_dur
            if trans in ("glitch", "flash"):
                sfx_list.append((generate_sfx("whoosh", duration=0.5, amplitude=0.5), trans_time - 0.2))
            elif trans == "swipe":
                sfx_list.append((generate_sfx("swoosh", duration=0.4, amplitude=0.4), trans_time - 0.1))
            
            current_time += seg_dur
        
        # Mix audio
        audio_path = output_path.replace(".mp4", "_audio.wav")
        mix_audio(bg_music, sfx_list, voiceover_array=None, output_path=audio_path)
        
        # Combine video + audio
        add_audio_to_video(video_only_path, audio_path, output_path)
        
        # Clean up temp files
        if os.path.exists(video_only_path):
            os.remove(video_only_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)
    except Exception as e:
        print(f"Warning: Audio generation failed ({e}), using video without audio")
        if os.path.exists(video_only_path):
            os.rename(video_only_path, output_path)
    
    # Cleanup
    final_with_overlays.close()
    final.close()
    for c in clips:
        try:
            c.close()
        except Exception:
            pass
    
    return output_path


def render_long_form_video(
    script: dict,
    output_path: str,
    use_tts: bool = False,
    product_name: str = "",
    price: str = "",
    series_name: str = "",
) -> str:
    """Render a long-form (YouTube) video from script JSON."""
    
    WIDTH, HEIGHT = 1920, 1080  # 16:9 landscape
    FPS = 30
    
    chapters = script.get("chapters", [])
    if not chapters:
        raise ValueError("No chapters found in script")
    
    accent_color = BRAND_ACCENT
    base_bg = BRAND_BG
    
    total_chapters = len(chapters)
    total_segments = sum(len(ch.get("segments", [])) for ch in chapters)
    
    all_clips = []
    
    # ── Branded Intro (3 seconds for long form) ──
    intro_frame = render_branded_intro(WIDTH, HEIGHT, series_name, product_name)
    intro_clip = ImageClip(intro_frame, duration=3.0)
    intro_clip = intro_clip.with_effects([vfx.FadeIn(0.5), vfx.FadeOut(0.5)])
    all_clips.append(intro_clip)
    
    segment_counter = 0
    engagement_inserted = False
    
    for ch_idx, chapter in enumerate(chapters):
        chapter_name = chapter.get("chapter_name", "")
        segments = chapter.get("segments", [])
        
        # ── Section header overlay for chapter ──
        # Detect section type from chapter name
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
        
        # Chapter title card with section header
        chapter_frame = render_text_frame(
            text=chapter_name.upper(),
            width=WIDTH, height=HEIGHT,
            text_color=accent_color,
            bg_color=base_bg,
            text_style="headline_bold",
            is_short_form=False,
            accent_color=accent_color,
        )
        
        # Composite section header onto chapter card if applicable
        if section_type:
            header_overlay = render_section_header(WIDTH, HEIGHT, section_type, accent_color)
            chapter_pil = Image.fromarray(chapter_frame).convert("RGBA")
            chapter_pil = Image.alpha_composite(chapter_pil, header_overlay)
            chapter_frame = np.array(chapter_pil.convert("RGB"))
        
        chapter_clip = ImageClip(chapter_frame, duration=2.5)
        chapter_clip = chapter_clip.with_effects([vfx.FadeIn(0.4), vfx.FadeOut(0.4)])
        all_clips.append(chapter_clip)
        
        # ── Render chapter segments ──
        rendered_frames = []
        segment_clips_ch = []
        
        for seg in segments:
            clip = build_segment_clip(seg, WIDTH, HEIGHT, False, accent_color, base_bg)
            segment_clips_ch.append(clip)
            
            frame = render_text_frame(
                text=seg.get("text", ""),
                width=WIDTH, height=HEIGHT,
                text_color=ensure_readable_color(
                    hex_to_rgb(seg.get("text_color", "#FFFFFF")) if seg.get("text_color") else (255, 255, 255),
                    base_bg
                ),
                bg_color=base_bg,
                text_style=seg.get("text_style", "subtitle"),
                is_short_form=False,
                accent_color=accent_color,
            )
            rendered_frames.append(frame)
            segment_counter += 1
        
        # Interleave segments with transitions
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
        
        # ── Engagement bait: insert poll/comment prompt mid-video ──
        if not engagement_inserted and ch_idx >= total_chapters // 2:
            # Insert a comment prompt card
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
    
    # Concatenate all clips
    final = concatenate_videoclips(all_clips, method="compose")
    
    # ── Persistent overlays: watermark + lower third + progress bar ──
    overlay_layers = [final]
    
    # Watermark
    watermark = render_watermark_overlay(WIDTH, HEIGHT)
    watermark_arr = np.array(watermark.convert("RGBA"))
    watermark_clip = ImageClip(watermark_arr, duration=final.duration)
    overlay_layers.append(watermark_clip)
    
    # Lower third (if product name provided)
    if product_name:
        lower_third = render_lower_third(WIDTH, HEIGHT, product_name, price, is_short_form=False)
        lt_arr = np.array(lower_third.convert("RGBA"))
        lt_clip = ImageClip(lt_arr, duration=final.duration)
        overlay_layers.append(lt_clip)
    
    # Progress bar overlay (animated)
    def make_progress_frame(t):
        progress = t / max(final.duration, 1)
        overlay = render_progress_overlay(WIDTH, HEIGHT, progress, accent_color=accent_color)
        return np.array(overlay.convert("RGBA"))
    
    progress_base = ImageClip(
        make_progress_frame(0), duration=final.duration
    ).transform(lambda get_frame, t: make_progress_frame(t))
    overlay_layers.append(progress_base)
    
    final_with_overlays = CompositeVideoClip(overlay_layers)
    
    # Write video (without audio first)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    video_only_path = output_path.replace(".mp4", "_video_only.mp4")
    final_with_overlays.write_videofile(
        video_only_path,
        fps=FPS,
        codec="libx264",
        audio=False,
        preset="ultrafast",
        threads=4,
        logger=None,
    )
    
    # ── Generate and add audio ──
    try:
        video_duration = final.duration
        
        # Generate background music (chill for long-form)
        bg_music = generate_background_music(video_duration, mood="chill", tempo=80)
        
        # Generate SFX timed to chapter transitions and key moments
        sfx_list = []
        current_time = 3.0  # After intro
        
        for ch_idx, chapter in enumerate(chapters):
            # Chapter transition ding
            sfx_list.append((generate_sfx("ding", duration=0.5, amplitude=0.5), current_time))
            current_time += 2.5  # Chapter title card duration
            
            for seg in chapter.get("segments", []):
                seg_dur = seg.get("duration", 4.0)
                anim = seg.get("animation", "fade_in")
                trans = seg.get("transition_to_next", "fade")
                
                # Text reveal SFX
                if anim in ("word_by_word", "typewriter"):
                    sfx_list.append((generate_sfx("pop", duration=0.1, amplitude=0.3), current_time + 0.1))
                elif anim in ("impact_scale", "shake"):
                    sfx_list.append((generate_sfx("bass_drop", duration=0.8, amplitude=0.4), current_time))
                elif anim in ("slide_up", "slide_left"):
                    sfx_list.append((generate_sfx("swoosh", duration=0.4, amplitude=0.3), current_time))
                elif anim == "highlight_sweep":
                    sfx_list.append((generate_sfx("whoosh", duration=0.4, amplitude=0.3), current_time))
                
                # Transition SFX
                trans_time = current_time + seg_dur
                if trans in ("glitch", "flash"):
                    sfx_list.append((generate_sfx("whoosh", duration=0.5, amplitude=0.4), trans_time - 0.2))
                elif trans == "swipe":
                    sfx_list.append((generate_sfx("swoosh", duration=0.4, amplitude=0.3), trans_time - 0.1))
                elif trans == "zoom":
                    sfx_list.append((generate_sfx("bass_drop", duration=0.6, amplitude=0.3), trans_time - 0.1))
                
                current_time += seg_dur
        
        # Mix audio
        audio_path = output_path.replace(".mp4", "_audio.wav")
        mix_audio(bg_music, sfx_list, voiceover_array=None, output_path=audio_path)
        
        # Combine video + audio
        add_audio_to_video(video_only_path, audio_path, output_path)
        
        # Clean up temp files
        if os.path.exists(video_only_path):
            os.remove(video_only_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)
    except Exception as e:
        print(f"Warning: Audio generation failed ({e}), using video without audio")
        if os.path.exists(video_only_path):
            os.rename(video_only_path, output_path)
    
    # Cleanup
    final_with_overlays.close()
    final.close()
    for c in all_clips:
        try:
            c.close()
        except Exception:
            pass
    
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
