import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np

from content_styles import human_style_name
from visual_quality import measure_image_contrast, measure_pil_contrast

# Brand colors
DARK_PINK = (196, 80, 122)
NEAR_BLACK = (10, 10, 15)
WHITE = (255, 255, 255)
STROKE_BLACK = (0, 0, 0)

# Font paths
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
FONT_BOLD = os.path.join(ASSETS_DIR, "Montserrat-Bold.ttf")
FONT_BLACK = os.path.join(ASSETS_DIR, "Montserrat-Black.ttf")
FONT_REGULAR = os.path.join(ASSETS_DIR, "Montserrat-Regular.ttf")
FALLBACK_FONT = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"

# Thumbnail dimensions
WIDTH, HEIGHT = 1280, 720

MIN_TITLE_FONT = 72
MIN_SUBTITLE_FONT = 44
MAX_TITLE_CHARS = 34
MAX_SUBTITLE_CHARS = 28
TITLE_STROKE = 6
SUBTITLE_STROKE = 4
ACCENT_BAR_WIDTH = 88


def _font_path(preferred: str) -> str:
    if preferred and os.path.isfile(preferred):
        return preferred
    if os.path.isfile(FALLBACK_FONT):
        return FALLBACK_FONT
    return preferred


def _load_font(font_file: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = _font_path(font_file)
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def punchy_text(text: str, max_chars: int = MAX_TITLE_CHARS, max_lines: int = 2) -> str:
    """Truncate/wrap marketing copy into short, readable thumbnail lines."""
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return ""
    if len(cleaned) <= max_chars and max_lines == 1:
        return cleaned
    words = cleaned.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if len(trial) <= max_chars:
            current = trial
            continue
        if current:
            lines.append(current)
            if len(lines) >= max_lines:
                current = ""
                break
        if len(word) > max_chars:
            current = word[: max_chars - 1].rstrip() + "…"
            lines.append(current)
            current = ""
            if len(lines) >= max_lines:
                break
        else:
            current = word
    if current and len(lines) < max_lines:
        lines.append(current)
    if not lines:
        return cleaned[:max_chars]
    return "\n".join(lines[:max_lines])


def _fit_font_size(text: str, font_path: str, max_width: int, max_height: int, draw_obj, min_size: int) -> int:
    size = max(min_size, 1)
    font = _load_font(font_path, size)
    bbox = draw_obj.multiline_textbbox((0, 0), text, font=font, spacing=8)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    while tw < max_width and th < max_height:
        size += 2
        font = _load_font(font_path, size)
        bbox = draw_obj.multiline_textbbox((0, 0), text, font=font, spacing=8)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if size > 220:
            break
    fitted = max(min_size, size - 2)
    # If still overflowing at min size, caller should have truncated; keep min floor.
    return fitted


def _draw_text(
    draw_obj,
    xy,
    text: str,
    font,
    fill=WHITE,
    stroke_width: int = TITLE_STROKE,
    stroke_fill=STROKE_BLACK,
    align: str = "center",
):
    draw_obj.multiline_text(
        xy,
        text,
        font=font,
        fill=fill,
        align=align,
        spacing=8,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


def generate_thumbnail(title, subtitle="", style="bold_text", accent_color=DARK_PINK, output_path=None):
    title = punchy_text(title, MAX_TITLE_CHARS, 2)
    subtitle = punchy_text(subtitle, MAX_SUBTITLE_CHARS, 2) if subtitle else ""

    img = Image.new("RGB", (WIDTH, HEIGHT), NEAR_BLACK)
    draw = ImageDraw.Draw(img)

    def add_gradient_and_particles(image_obj):
        for y in range(HEIGHT):
            r = int(NEAR_BLACK[0] * (1 - y / HEIGHT) + 0 * (y / HEIGHT))
            g = int(NEAR_BLACK[1] * (1 - y / HEIGHT) + 0 * (y / HEIGHT))
            b = int(NEAR_BLACK[2] * (1 - y / HEIGHT) + 0 * (y / HEIGHT))
            draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

        pixels = np.array(image_obj)
        noise = np.random.randint(-4, 4, pixels.shape, dtype=np.int16)
        pixels = np.clip(pixels + noise, 0, 255).astype(np.uint8)
        return Image.fromarray(pixels)

    img = add_gradient_and_particles(img)
    draw = ImageDraw.Draw(img)

    def _white_underline(x, y, width, height=18):
        draw.rectangle([(x, y), (x + width, y + height)], fill=WHITE)

    if style == "bold_text":
        max_title_width = int(WIDTH * 0.92)
        max_title_height = int(HEIGHT * 0.58)
        title_font_size = _fit_font_size(title, FONT_BLACK, max_title_width, max_title_height, draw, MIN_TITLE_FONT)
        title_font = _load_font(FONT_BLACK, title_font_size)
        title_bbox = draw.multiline_textbbox((0, 0), title, font=title_font, spacing=8)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]
        title_x = (WIDTH - title_width) / 2
        title_y = (HEIGHT - title_height) / 2 - (48 if subtitle else 0)
        _draw_text(draw, (title_x, title_y), title, title_font, fill=WHITE, stroke_width=TITLE_STROKE)
        _white_underline(title_x, title_y + title_height + 16, title_width, 20)

        if subtitle:
            sub_size = _fit_font_size(
                subtitle, FONT_BOLD, int(WIDTH * 0.88), int(HEIGHT * 0.2), draw, MIN_SUBTITLE_FONT
            )
            sub_font = _load_font(FONT_BOLD, sub_size)
            sub_bbox = draw.multiline_textbbox((0, 0), subtitle, font=sub_font, spacing=6)
            sub_w = sub_bbox[2] - sub_bbox[0]
            sub_x = (WIDTH - sub_w) / 2
            sub_y = title_y + title_height + 48
            _draw_text(
                draw, (sub_x, sub_y), subtitle, sub_font, fill=WHITE, stroke_width=SUBTITLE_STROKE
            )

    elif style == "split":
        draw.rectangle([(WIDTH - ACCENT_BAR_WIDTH, 0), (WIDTH, HEIGHT)], fill=accent_color)
        text_area_width = WIDTH - ACCENT_BAR_WIDTH

        max_title_width = int(text_area_width * 0.9)
        max_title_height = int(HEIGHT * 0.5)
        title_font_size = _fit_font_size(title, FONT_BLACK, max_title_width, max_title_height, draw, MIN_TITLE_FONT)
        title_font = _load_font(FONT_BLACK, title_font_size)
        title_bbox = draw.multiline_textbbox((0, 0), title, font=title_font, spacing=8)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]
        title_x = (text_area_width - title_width) / 2
        title_y = (HEIGHT - title_height) / 2 - (title_height / 5)
        _draw_text(draw, (title_x, title_y), title, title_font, fill=WHITE, stroke_width=TITLE_STROKE)
        _white_underline(title_x, title_y + title_height + 14, title_width, 18)

        if subtitle:
            max_subtitle_width = int(text_area_width * 0.88)
            subtitle_font_size = _fit_font_size(
                subtitle, FONT_BOLD, max_subtitle_width, int(HEIGHT * 0.22), draw, MIN_SUBTITLE_FONT
            )
            subtitle_font = _load_font(FONT_BOLD, subtitle_font_size)
            subtitle_bbox = draw.multiline_textbbox((0, 0), subtitle, font=subtitle_font, spacing=6)
            subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
            subtitle_x = (text_area_width - subtitle_width) / 2
            subtitle_y = title_y + title_height + 44
            _draw_text(
                draw,
                (subtitle_x, subtitle_y),
                subtitle,
                subtitle_font,
                fill=WHITE,
                stroke_width=SUBTITLE_STROKE,
            )

    elif style == "number":
        max_title_width = int(WIDTH * 0.55)
        max_title_height = int(HEIGHT * 0.55)
        title_font_size = _fit_font_size(title, FONT_BLACK, max_title_width, max_title_height, draw, MIN_TITLE_FONT)
        title_font = _load_font(FONT_BLACK, title_font_size)
        title_bbox = draw.multiline_textbbox((0, 0), title, font=title_font, spacing=8)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]
        title_x = (WIDTH - title_width) / 2
        title_y = (HEIGHT - title_height) / 2 - (title_height / 4)
        _draw_text(
            draw,
            (title_x, title_y),
            title,
            title_font,
            fill=WHITE,
            stroke_width=TITLE_STROKE,
            stroke_fill=STROKE_BLACK,
        )
        _white_underline(title_x, title_y + title_height + 12, title_width, 16)
        draw.rectangle(
            [
                (title_x, title_y + title_height + 34),
                (title_x + min(title_width, 220), title_y + title_height + 46),
            ],
            fill=accent_color,
        )

        if subtitle:
            max_subtitle_width = int(WIDTH * 0.88)
            subtitle_font_size = _fit_font_size(
                subtitle, FONT_BOLD, max_subtitle_width, int(HEIGHT * 0.2), draw, MIN_SUBTITLE_FONT
            )
            subtitle_font = _load_font(FONT_BOLD, subtitle_font_size)
            subtitle_bbox = draw.multiline_textbbox((0, 0), subtitle, font=subtitle_font, spacing=6)
            subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
            subtitle_x = (WIDTH - subtitle_width) / 2
            subtitle_y = title_y + title_height + 56
            _draw_text(
                draw,
                (subtitle_x, subtitle_y),
                subtitle,
                subtitle_font,
                fill=WHITE,
                stroke_width=SUBTITLE_STROKE,
            )

    elif style == "vs":
        left_text_area_width = int(WIDTH * 0.4)
        max_title_height = int(HEIGHT * 0.55)
        title1_font_size = _fit_font_size(
            title, FONT_BLACK, left_text_area_width, max_title_height, draw, MIN_TITLE_FONT
        )
        title1_font = _load_font(FONT_BLACK, title1_font_size)
        title1_bbox = draw.multiline_textbbox((0, 0), title, font=title1_font, spacing=8)
        title1_width = title1_bbox[2] - title1_bbox[0]
        title1_height = title1_bbox[3] - title1_bbox[1]
        title1_x = (left_text_area_width - title1_width) / 2
        title1_y = (HEIGHT - title1_height) / 2
        _draw_text(draw, (title1_x, title1_y), title, title1_font, fill=WHITE, stroke_width=TITLE_STROKE)

        vs_font_size = _fit_font_size("VS", FONT_BLACK, int(WIDTH * 0.15), int(HEIGHT * 0.3), draw, MIN_TITLE_FONT)
        vs_font = _load_font(FONT_BLACK, vs_font_size)
        vs_bbox = draw.multiline_textbbox((0, 0), "VS", font=vs_font, spacing=8)
        vs_width = vs_bbox[2] - vs_bbox[0]
        vs_height = vs_bbox[3] - vs_bbox[1]
        vs_x = (WIDTH - vs_width) / 2
        vs_y = (HEIGHT - vs_height) / 2
        _draw_text(
            draw,
            (vs_x, vs_y),
            "VS",
            vs_font,
            fill=accent_color,
            stroke_width=TITLE_STROKE,
            stroke_fill=STROKE_BLACK,
        )

        right_text = punchy_text(subtitle, MAX_TITLE_CHARS, 2) if subtitle else ""
        right_text_area_width = int(WIDTH * 0.4)
        title2_font_size = _fit_font_size(
            right_text, FONT_BLACK, right_text_area_width, max_title_height, draw, MIN_TITLE_FONT
        )
        title2_font = _load_font(FONT_BLACK, title2_font_size)
        title2_bbox = draw.multiline_textbbox((0, 0), right_text, font=title2_font, spacing=8)
        title2_width = title2_bbox[2] - title2_bbox[0]
        title2_height = title2_bbox[3] - title2_bbox[1]
        title2_x = WIDTH - right_text_area_width + (right_text_area_width - title2_width) / 2
        title2_y = (HEIGHT - title2_height) / 2
        _draw_text(draw, (title2_x, title2_y), right_text, title2_font, fill=WHITE, stroke_width=TITLE_STROKE)

    elif style == "list":
        list_items = [item.strip() for item in subtitle.split(",") if item.strip()][:5]
        y_offset = int(HEIGHT * 0.1)
        line_height = int(HEIGHT * 0.1)

        max_title_width = int(WIDTH * 0.9)
        max_title_height = int(HEIGHT * 0.18)
        title_font_size = _fit_font_size(title, FONT_BLACK, max_title_width, max_title_height, draw, MIN_TITLE_FONT)
        title_font = _load_font(FONT_BLACK, title_font_size)
        title_bbox = draw.multiline_textbbox((0, 0), title, font=title_font, spacing=8)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (WIDTH - title_width) / 2
        _draw_text(
            draw,
            (title_x, y_offset),
            title,
            title_font,
            fill=accent_color,
            stroke_width=TITLE_STROKE,
            stroke_fill=STROKE_BLACK,
        )
        y_offset += title_bbox[3] - title_bbox[1] + 28

        for i, item in enumerate(list_items):
            display_text = punchy_text(f"{i + 1}. {item}", MAX_TITLE_CHARS, 1)
            item_font_size = _fit_font_size(
                display_text, FONT_BOLD, int(WIDTH * 0.85), int(line_height * 0.85), draw, MIN_SUBTITLE_FONT
            )
            item_font = _load_font(FONT_BOLD, item_font_size)
            item_bbox = draw.multiline_textbbox((0, 0), display_text, font=item_font, spacing=6)
            item_width = item_bbox[2] - item_bbox[0]
            item_x = (WIDTH - item_width) / 2
            _draw_text(
                draw,
                (item_x, y_offset),
                display_text,
                item_font,
                fill=WHITE,
                stroke_width=SUBTITLE_STROKE,
            )
            y_offset += line_height

    if output_path:
        img.save(output_path)
        return None
    return img


def add_badge(image, badge_text, position="top_right", color=DARK_PINK):
    draw = ImageDraw.Draw(image)
    badge_font_size = MIN_SUBTITLE_FONT
    badge_font = _load_font(FONT_BOLD, badge_font_size)
    while draw.textbbox((0, 0), badge_text, font=badge_font)[2] < image.width / 5 and badge_font_size < 100:
        badge_font_size += 1
        badge_font = _load_font(FONT_BOLD, badge_font_size)
    badge_font_size = max(MIN_SUBTITLE_FONT, badge_font_size - 1)
    badge_font = _load_font(FONT_BOLD, badge_font_size)

    badge_bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
    badge_width = badge_bbox[2] - badge_bbox[0]
    badge_height = badge_bbox[3] - badge_bbox[1]

    padding = 20
    margin = 30

    if position == "top_right":
        x = image.width - badge_width - padding - margin
        y = margin
    elif position == "top_left":
        x = margin
        y = margin
    elif position == "bottom_right":
        x = image.width - badge_width - padding - margin
        y = image.height - badge_height - padding - margin
    elif position == "bottom_left":
        x = margin
        y = image.height - badge_height - padding - margin
    else:
        x, y = margin, margin

    draw.rectangle(
        [(x - padding, y - padding), (x + badge_width + padding, y + badge_height + padding)],
        fill=color,
    )
    _draw_text(
        draw,
        (x, y),
        badge_text,
        badge_font,
        fill=WHITE,
        stroke_width=2,
        stroke_fill=STROKE_BLACK,
        align="left",
    )

    return image


def select_best_contrast_variant(variants: dict) -> str:
    """Return variant key with highest measured contrast (A/B/C)."""
    best_key = next(iter(variants), "variant_a")
    best_ratio = -1.0
    for key, img in variants.items():
        metrics = None
        if isinstance(img, Image.Image):
            metrics = measure_pil_contrast(img)
        elif img is not None:
            path = str(img)
            if os.path.isfile(path):
                metrics = measure_image_contrast(path)
        if not metrics:
            continue
        ratio = float(metrics.get("contrast_ratio") or 0)
        if ratio > best_ratio:
            best_ratio = ratio
            best_key = key
    return best_key


def generate_thumbnail_set(
    product_name,
    hook_type,
    content_style,
    keywords=None,
    product_image_path=None,
    thumbnail_text_primary=None,
    thumbnail_text_secondary=None,
):
    variants = {}
    style_label = human_style_name(content_style)
    primary = punchy_text(
        thumbnail_text_primary or f"{product_name} Review",
        MAX_TITLE_CHARS,
        2,
    )
    secondary = punchy_text(
        thumbnail_text_secondary or f"{hook_type} | Worth It?",
        MAX_SUBTITLE_CHARS,
        2,
    )

    variants["variant_a"] = generate_thumbnail(
        title=primary,
        subtitle=secondary,
        style="bold_text",
        accent_color=DARK_PINK,
    )

    variants["variant_b"] = generate_thumbnail(
        title=punchy_text(f"Is {product_name} Worth It?", MAX_TITLE_CHARS, 2)
        if not thumbnail_text_primary
        else primary,
        subtitle=secondary if thumbnail_text_secondary else punchy_text(f"Unbiased {style_label}", MAX_SUBTITLE_CHARS, 2),
        style="split",
        accent_color=DARK_PINK,
    )

    if keywords and len(keywords) > 0:
        variants["variant_c"] = generate_thumbnail(
            title=punchy_text(str(keywords[0]).upper(), MAX_TITLE_CHARS, 1),
            subtitle=punchy_text(f"{product_name} {style_label}", MAX_SUBTITLE_CHARS, 2),
            style="number",
            accent_color=DARK_PINK,
        )
    else:
        variants["variant_c"] = generate_thumbnail(
            title=primary,
            subtitle=secondary,
            style="bold_text",
            accent_color=DARK_PINK,
        )

    if product_image_path:
        from product_media import thumbnail_with_product_hero

        for key in ("variant_a", "variant_b"):
            variants[key] = thumbnail_with_product_hero(variants[key], product_image_path)

    return variants


if __name__ == "__main__":
    if not os.path.exists(ASSETS_DIR):
        os.makedirs(ASSETS_DIR)

    print("Generating sample thumbnails...")
    generate_thumbnail(title="THE BEST SMARTPHONE OF 2024", style="bold_text", output_path="sample_bold_text.png")
    print("Generated sample_bold_text.png")
    generate_thumbnail(
        title="TOP 5 GAMING LAPTOPS",
        accent_color=(0, 150, 255),
        style="bold_text",
        output_path="sample_bold_text_blue.png",
    )
    print("Generated sample_bold_text_blue.png")
    generate_thumbnail(title="ULTIMATE GUIDE", subtitle="To Smart Home Devices", style="split", output_path="sample_split.png")
    print("Generated sample_split.png")
    generate_thumbnail(title="10X", subtitle="Your Productivity Today!", style="number", output_path="sample_number.png")
    print("Generated sample_number.png")
    generate_thumbnail(title="iPhone 15 Pro", subtitle="Galaxy S24 Ultra", style="vs", output_path="sample_vs.png")
    print("Generated sample_vs.png")
    generate_thumbnail(
        title="TOP 5 FEATURES",
        subtitle="Fast Charging, Long Battery Life, AI Camera, Foldable Screen, Gaming Performance",
        style="list",
        output_path="sample_list.png",
    )
    print("Generated sample_list.png")

    badge_test_img = generate_thumbnail(title="LIMITED TIME OFFER", style="bold_text", output_path=None)
    add_badge(badge_test_img, "NEW", position="top_right").save("sample_badge_new.png")
    print("Generated sample_badge_new.png")

    product = "Wireless Earbuds"
    thumbnail_set = generate_thumbnail_set(
        product,
        "Game Changer",
        "honest_review",
        keywords=["99", "Sound Quality"],
        thumbnail_text_primary="Earbuds Review",
        thumbnail_text_secondary="$79 | Worth It?",
    )
    best = select_best_contrast_variant(thumbnail_set)
    print(f"Best contrast variant: {best}")
    for variant_name, img_obj in thumbnail_set.items():
        img_obj.save(f"sample_set_{variant_name}.png")
        print(f"Generated sample_set_{variant_name}.png")
    print("Thumbnail generation complete.")
