import os
import math
import random
import textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy import (
    ImageClip,
    CompositeVideoClip,
    ColorClip,
    concatenate_videoclips,
    vfx,
)

# Absolute asset fonts (must match video_renderer / brand_overlays)
_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
FONT_BOLD = os.path.join(_ASSETS_DIR, "Montserrat-Bold.ttf")
if not os.path.exists(FONT_BOLD):
    print(f"Warning: Montserrat Bold missing at {FONT_BOLD}; falling back to NotoSans")
    FONT_BOLD = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"

def get_font(font_path, size):
    try:
        return ImageFont.truetype(font_path, size)
    except Exception:
        return ImageFont.truetype(FONT_BOLD, size)

def hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return (255, 255, 255)

def create_base_bg(width, height, bg_color):
    return Image.new("RGBA", (width, height), (*bg_color, 255))

# 1. Word by Word
def create_word_by_word_clip(text, width, height, duration, text_color, bg_color, accent_color, font_path, is_short_form):
    base_font_size = int(width * 0.055) if is_short_form else int(width * 0.04)
    font = get_font(font_path, base_font_size)
    
    words = text.split()
    if not words:
        return ColorClip(size=(width, height), color=bg_color, duration=duration)
        
    word_duration = duration / len(words)
    clips = []
    
    # Simple word wrapping logic for positions
    max_width = width * 0.8
    lines = []
    current_line = []
    current_width = 0
    
    # Dummy draw for text measurement
    dummy_img = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    
    space_width = draw.textlength(" ", font=font)
    
    for word in words:
        w = draw.textlength(word, font=font)
        if current_width + w > max_width and current_line:
            lines.append(current_line)
            current_line = [(word, w)]
            current_width = w + space_width
        else:
            current_line.append((word, w))
            current_width += w + space_width
    if current_line:
        lines.append(current_line)
        
    # Calculate total height
    line_height = base_font_size * 1.2
    total_height = len(lines) * line_height
    start_y = (height - total_height) / 2
    
    # Create clips for each word
    word_clips = []
    current_time = 0
    
    for i, line in enumerate(lines):
        line_width = sum(w for _, w in line) + space_width * (len(line) - 1)
        start_x = (width - line_width) / 2
        
        current_x = start_x
        for word, w in line:
            # Create image for this word
            img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Draw outline
            stroke_color = (0, 0, 0, 200)
            for dx, dy in [(-2,0),(2,0),(0,-2),(0,2),(-1,-1),(1,1),(-1,1),(1,-1)]:
                draw.text((current_x + dx, start_y + i * line_height + dy), word, font=font, fill=stroke_color)
            
            # Draw text
            draw.text((current_x, start_y + i * line_height), word, font=font, fill=(*text_color, 255))
            
            word_clip = ImageClip(np.array(img)).with_start(current_time).with_duration(duration - current_time)
            # Fade in effect
            word_clip = word_clip.with_effects([vfx.FadeIn(min(0.1, word_duration))])
            word_clips.append(word_clip)
            
            current_x += w + space_width
            current_time += word_duration
            
    bg_clip = ColorClip(size=(width, height), color=bg_color, duration=duration)
    return CompositeVideoClip([bg_clip] + word_clips)

# 2. Typewriter
def create_typewriter_clip(text, width, height, duration, text_color, bg_color, accent_color, font_path, is_short_form):
    base_font_size = int(width * 0.055) if is_short_form else int(width * 0.04)
    font = get_font(font_path, base_font_size)
    
    max_chars = 25 if is_short_form else 35
    wrapped_text = textwrap.fill(text, width=max_chars)
    
    def make_frame(t):
        progress = min(1.0, t / (duration * 0.8)) # Finish typing at 80% of duration
        chars_to_show = int(progress * len(wrapped_text))
        current_text = wrapped_text[:chars_to_show]
        
        # Blinking cursor
        if t < duration * 0.8 or int(t * 4) % 2 == 0:
            current_text += "|"
            
        img = Image.new("RGBA", (width, height), (*bg_color, 255))
        draw = ImageDraw.Draw(img)
        
        bbox = draw.multiline_textbbox((0, 0), wrapped_text + "|", font=font, align="center")
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (width - text_w) // 2
        y = (height - text_h) // 2
        
        # Draw outline
        stroke_color = (0, 0, 0, 200)
        for dx, dy in [(-2,0),(2,0),(0,-2),(0,2),(-1,-1),(1,1),(-1,1),(1,-1)]:
            draw.multiline_text((x + dx, y + dy), current_text, font=font, fill=stroke_color, align="center")
            
        draw.multiline_text((x, y), current_text, font=font, fill=(*text_color, 255), align="center")
        return np.array(img.convert("RGB"))
        
    return ImageClip(make_frame(0)).with_duration(duration).transform(lambda get_frame, t: make_frame(t))

# 3. Impact Scale
def create_impact_scale_clip(text, width, height, duration, text_color, bg_color, accent_color, font_path, is_short_form):
    base_font_size = int(width * 0.08) if is_short_form else int(width * 0.06)
    font = get_font(font_path, base_font_size)
    
    # Render base text image
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center")
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (width - text_w) // 2
    y = (height - text_h) // 2
    
    # Draw outline
    stroke_color = (0, 0, 0, 200)
    for dx, dy in [(-2,0),(2,0),(0,-2),(0,2),(-1,-1),(1,1),(-1,1),(1,-1)]:
        draw.multiline_text((x + dx, y + dy), text, font=font, fill=stroke_color, align="center")
        
    draw.multiline_text((x, y), text, font=font, fill=(*text_color, 255), align="center")
    base_arr = np.array(img)
    
    bg_clip = ColorClip(size=(width, height), color=bg_color, duration=duration)
    
    def scale_effect(get_frame, t):
        # Bounce effect: 1.5 -> 0.9 -> 1.0
        if t < 0.2:
            scale = 1.5 - (0.6 * (t / 0.2))
        elif t < 0.3:
            scale = 0.9 + (0.1 * ((t - 0.2) / 0.1))
        else:
            scale = 1.0
            
        frame = base_arr
        h, w = frame.shape[:2]
        new_h, new_w = int(h * scale), int(w * scale)
        
        pil_img = Image.fromarray(frame)
        pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
        
        # Center crop or pad
        result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        left = (w - new_w) // 2
        top = (h - new_h) // 2
        result.paste(pil_img, (left, top))
        
        return np.array(result)
        
    text_clip = ImageClip(base_arr).with_duration(duration).transform(scale_effect)
    return CompositeVideoClip([bg_clip, text_clip])

# 4. Highlight Sweep
def create_highlight_sweep_clip(text, width, height, duration, text_color, bg_color, accent_color, font_path, is_short_form):
    base_font_size = int(width * 0.055) if is_short_form else int(width * 0.04)
    font = get_font(font_path, base_font_size)
    
    max_chars = 25 if is_short_form else 35
    wrapped_text = textwrap.fill(text, width=max_chars)
    
    dummy_img = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font, align="center")
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (width - text_w) // 2
    y = (height - text_h) // 2
    
    def make_frame(t):
        img = Image.new("RGBA", (width, height), (*bg_color, 255))
        draw = ImageDraw.Draw(img)
        
        # Sweep progress
        sweep_duration = min(0.5, duration * 0.5)
        progress = min(1.0, t / sweep_duration)
        
        # Draw highlight bar
        bar_width = int(text_w * progress)
        padding = 10
        draw.rectangle(
            [x - padding, y - padding, x + bar_width + padding, y + text_h + padding],
            fill=(*accent_color, 255)
        )
        
        # Draw outline
        stroke_color = (0, 0, 0, 200)
        for dx, dy in [(-2,0),(2,0),(0,-2),(0,2),(-1,-1),(1,1),(-1,1),(1,-1)]:
            draw.multiline_text((x + dx, y + dy), wrapped_text, font=font, fill=stroke_color, align="center")
            
        draw.multiline_text((x, y), wrapped_text, font=font, fill=(*text_color, 255), align="center")
        return np.array(img.convert("RGB"))
        
    return ImageClip(make_frame(0)).with_duration(duration).transform(lambda get_frame, t: make_frame(t))

# 5. Shake
def create_shake_clip(base_frame, duration, intensity=5):
    def shake_effect(get_frame, t):
        if t > 0.3:
            return base_frame
            
        dx = random.randint(-intensity, intensity)
        dy = random.randint(-intensity, intensity)
        
        img = Image.fromarray(base_frame)
        result = Image.new("RGB", img.size)
        result.paste(img, (dx, dy))
        return np.array(result)
        
    return ImageClip(base_frame).with_duration(duration).transform(shake_effect)

# 6. Slide Up
def create_slide_up_clip(base_frame, width, height, duration):
    def slide_effect(get_frame, t):
        slide_duration = min(0.4, duration * 0.3)
        if t >= slide_duration:
            return base_frame
            
        progress = t / slide_duration
        # Ease out cubic
        ease = 1 - pow(1 - progress, 3)
        
        y_offset = int(height * (1 - ease))
        
        img = Image.fromarray(base_frame)
        result = Image.new("RGB", (width, height), (0, 0, 0))
        result.paste(img, (0, y_offset))
        return np.array(result)
        
    return ImageClip(base_frame).with_duration(duration).transform(slide_effect)

# 7. Slide Left
def create_slide_left_clip(base_frame, width, height, duration):
    def slide_effect(get_frame, t):
        slide_duration = min(0.4, duration * 0.3)
        if t >= slide_duration:
            return base_frame
            
        progress = t / slide_duration
        # Ease out cubic
        ease = 1 - pow(1 - progress, 3)
        
        x_offset = int(width * (1 - ease))
        
        img = Image.fromarray(base_frame)
        result = Image.new("RGB", (width, height), (0, 0, 0))
        result.paste(img, (x_offset, 0))
        return np.array(result)
        
    return ImageClip(base_frame).with_duration(duration).transform(slide_effect)

# 8. Glitch Transition
def create_glitch_transition(frame_a, frame_b, duration=0.15):
    width, height = frame_a.shape[1], frame_a.shape[0]
    
    def effect(get_frame, t):
        if t >= duration:
            return frame_b
            
        progress = t / duration
        
        # RGB split and horizontal offset
        img_a = Image.fromarray(frame_a)
        img_b = Image.fromarray(frame_b)
        
        # Blend between frames
        blended_img = Image.blend(img_a.convert("RGBA"), img_b.convert("RGBA"), progress)
        
        # Apply glitch effect for a short period
        if t < duration * 0.8:
            glitch_offset = int(math.sin(t * 50) * 5 * (1 - progress))
            
            r, g, b, a = blended_img.split()
            
            # Shift channels
            r = Image.composite(r, r, Image.new('1', r.size, 0)).transform(r.size, Image.AFFINE, (1, 0, glitch_offset, 0, 1, 0))
            g = Image.composite(g, g, Image.new('1', g.size, 0)).transform(g.size, Image.AFFINE, (1, 0, -glitch_offset, 0, 1, 0))
            
            glitched_img = Image.merge('RGBA', (r, g, b, a))
            return np.array(glitched_img.convert("RGB"))
        
        return np.array(blended_img.convert("RGB"))
        
    return ImageClip(frame_a).with_duration(duration).transform(effect)

# 9. Flash Transition
def create_flash_transition(frame_a, frame_b, accent_color, duration=0.1):
    width, height = frame_a.shape[1], frame_a.shape[0]
    
    def effect(get_frame, t):
        if t >= duration:
            return frame_b
            
        progress = t / duration
        
        # Flash white/accent color in the middle
        if progress < 0.5:
            alpha = progress * 2  # 0 to 1
        else:
            alpha = (1 - progress) * 2 # 1 to 0
            
        flash_color = accent_color # Use accent color for flash
        
        flash_img = Image.new("RGB", (width, height), flash_color)
        
        img_a = Image.fromarray(frame_a)
        img_b = Image.fromarray(frame_b)
        
        # Blend from frame_a to flash, then flash to frame_b
        if progress < 0.5:
            blended = Image.blend(img_a.convert("RGBA"), flash_img.convert("RGBA"), alpha)
        else:
            blended = Image.blend(flash_img.convert("RGBA"), img_b.convert("RGBA"), alpha)
            
        return np.array(blended.convert("RGB"))
        
    return ImageClip(frame_a).with_duration(duration).transform(effect)

# 10. Swipe Transition
def create_swipe_transition(frame_a, frame_b, duration=0.3):
    width, height = frame_a.shape[1], frame_a.shape[0]
    
    def effect(get_frame, t):
        if t >= duration:
            return frame_b
            
        progress = t / duration
        
        img_a = Image.fromarray(frame_a)
        img_b = Image.fromarray(frame_b)
        
        # Calculate x-offset for frame_b
        x_offset = int(width * (1 - progress))
        
        result = Image.new("RGB", (width, height))
        result.paste(img_a.crop((0, 0, x_offset, height)), (0, 0))
        result.paste(img_b.crop((x_offset, 0, width, height)), (x_offset, 0))
        
        return np.array(result)
        
    return ImageClip(frame_a).with_duration(duration).transform(effect)

# 11. Zoom Transition
def create_zoom_transition(frame_a, frame_b, duration=0.2):
    width, height = frame_a.shape[1], frame_a.shape[0]
    
    def effect(get_frame, t):
        if t >= duration:
            return frame_b
            
        progress = t / duration
        
        # Zoom in on frame_a, then cut to frame_b
        if progress < 0.8: # Zoom in for 80% of duration
            scale = 1 + (progress / 0.8) * 0.5 # Scales from 1 to 1.5
            
            img_a = Image.fromarray(frame_a)
            new_w, new_h = int(width * scale), int(height * scale)
            
            zoomed_img = img_a.resize((new_w, new_h), Image.LANCZOS)
            
            # Center crop
            left = (new_w - width) // 2
            top = (new_h - height) // 2
            
            cropped_img = zoomed_img.crop((left, top, left + width, top + height))
            return np.array(cropped_img)
        else:
            return frame_b
            
    return ImageClip(frame_a).with_duration(duration).transform(effect)


if __name__ == "__main__":
    # Create dummy assets directory and font files for testing
    if not os.path.exists("assets"):
        os.makedirs("assets")
    # Create dummy font files if they don't exist
    try:
        ImageFont.truetype("./assets/Montserrat-Bold.ttf", 10)
    except IOError:
        print("Montserrat-Bold.ttf not found, creating a dummy font file.")
        # Create a dummy font file (this won't be a real font but will prevent errors)
        with open("./assets/Montserrat-Bold.ttf", "w") as f:
            f.write("dummy font")

    print("Generating test video...")
    WIDTH, HEIGHT = 1280, 720
    DURATION = 5 # seconds
    TEXT_COLOR = (255, 255, 255)
    BG_COLOR = (0, 0, 0)
    ACCENT_COLOR = (196, 80, 122) # #c4507a
    FONT_PATH = "./assets/Montserrat-Bold.ttf"

    # Test create_word_by_word_clip
    word_by_word_text = "This is a test of word by word animation."
    word_by_word_clip = create_word_by_word_clip(
        word_by_word_text, WIDTH, HEIGHT, DURATION,
        TEXT_COLOR, BG_COLOR, ACCENT_COLOR, FONT_PATH, False
    )
    word_by_word_clip.write_videofile("word_by_word_test.mp4", fps=24, codec="libx264")

    # Test create_glitch_transition
    # Need two frames for transition
    frame_a_img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 255))
    draw_a = ImageDraw.Draw(frame_a_img)
    font_a = get_font(FONT_PATH, 80)
    draw_a.text((WIDTH/4, HEIGHT/2), "Frame A", font=font_a, fill=(255,255,255))
    frame_a = np.array(frame_a_img)

    frame_b_img = Image.new("RGB", (WIDTH, HEIGHT), (255, 0, 0))
    draw_b = ImageDraw.Draw(frame_b_img)
    font_b = get_font(FONT_PATH, 80)
    draw_b.text((WIDTH/4, HEIGHT/2), "Frame B", font=font_b, fill=(255,255,255))
    frame_b = np.array(frame_b_img)

    glitch_clip = create_glitch_transition(frame_a, frame_b, duration=1.0)
    glitch_clip.write_videofile("glitch_transition_test.mp4", fps=24, codec="libx264")

    print("Test videos generated: word_by_word_test.mp4 and glitch_transition_test.mp4")
