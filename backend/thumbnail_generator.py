import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

from content_styles import human_style_name

# Brand colors
DARK_PINK = (196, 80, 122)
NEAR_BLACK = (10, 10, 15)
WHITE = (255, 255, 255)

# Font paths
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
FONT_BOLD = os.path.join(ASSETS_DIR, "Montserrat-Bold.ttf")
FONT_BLACK = os.path.join(ASSETS_DIR, "Montserrat-Black.ttf")
FONT_REGULAR = os.path.join(ASSETS_DIR, "Montserrat-Regular.ttf")
FALLBACK_FONT = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" # Common fallback on Linux

# Thumbnail dimensions
WIDTH, HEIGHT = 1280, 720

def generate_thumbnail(title, subtitle="", style="bold_text", accent_color=DARK_PINK, output_path=None):
    img = Image.new("RGB", (WIDTH, HEIGHT), NEAR_BLACK)
    draw = ImageDraw.Draw(img)

    # Add dark gradient background with subtle particles
    def add_gradient_and_particles(image_obj):
        # Gradient
        for y in range(HEIGHT):
            r = int(NEAR_BLACK[0] * (1 - y / HEIGHT) + 0 * (y / HEIGHT))
            g = int(NEAR_BLACK[1] * (1 - y / HEIGHT) + 0 * (y / HEIGHT))
            b = int(NEAR_BLACK[2] * (1 - y / HEIGHT) + 0 * (y / HEIGHT))
            draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

        # Subtle particles (noise)
        pixels = np.array(image_obj)
        noise = np.random.randint(-10, 10, pixels.shape, dtype=np.int16)
        pixels = np.clip(pixels + noise, 0, 255).astype(np.uint8)
        return Image.fromarray(pixels)

    img = add_gradient_and_particles(img)
    draw = ImageDraw.Draw(img) # Re-initialize draw object after image modification

    # Helper function to get font size that fits within a given width and height
    def get_font_size(text, font_path, max_width, max_height, draw_obj):
        font_size = 1
        font = ImageFont.truetype(font_path, font_size)
        text_width, text_height = draw_obj.textbbox((0,0), text, font=font)[2:]
        while text_width < max_width and text_height < max_height:
            font_size += 1
            font = ImageFont.truetype(font_path, font_size)
            text_width, text_height = draw_obj.textbbox((0,0), text, font=font)[2:]
        return font_size - 1

    if style == "bold_text":

        # Title
        max_title_width = int(WIDTH * 0.9)
        max_title_height = int(HEIGHT * 0.6)
        title_font_size = get_font_size(title, FONT_BLACK, max_title_width, max_title_height, draw)
        title_font = ImageFont.truetype(FONT_BLACK, title_font_size)
        title_bbox = draw.textbbox((0,0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]
        title_x = (WIDTH - title_width) / 2
        title_y = (HEIGHT - title_height) / 2
        draw.text((title_x, title_y), title, font=title_font, fill=WHITE, align="center")

        # Accent glow (simple version for now)
        accent_bar_height = 10
        accent_bar_width = title_width * 0.8
        accent_bar_x = (WIDTH - accent_bar_width) / 2
        accent_bar_y = title_y + title_height + 20
        draw.rectangle([(accent_bar_x, accent_bar_y), (accent_bar_x + accent_bar_width, accent_bar_y + accent_bar_height)], fill=accent_color)



    elif style == "split":
        # Text on left, accent block on right
        text_area_width = int(WIDTH * 0.6)
        accent_block_width = WIDTH - text_area_width

        # Draw accent block
        draw.rectangle([(text_area_width, 0), (WIDTH, HEIGHT)], fill=accent_color)

        # Title text
        max_title_width = int(text_area_width * 0.9)
        max_title_height = int(HEIGHT * 0.5)
        title_font_size = get_font_size(title, FONT_BLACK, max_title_width, max_title_height, draw)
        title_font = ImageFont.truetype(FONT_BLACK, title_font_size)
        title_bbox = draw.textbbox((0,0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]
        title_x = (text_area_width - title_width) / 2
        title_y = (HEIGHT - title_height) / 2 - (title_height / 4) # Slightly higher
        draw.text((title_x, title_y), title, font=title_font, fill=WHITE, align="center")

        # Subtitle text
        if subtitle:
            max_subtitle_width = int(text_area_width * 0.8)
            max_subtitle_height = int(HEIGHT * 0.2)
            subtitle_font_size = get_font_size(subtitle, FONT_REGULAR, max_subtitle_width, max_subtitle_height, draw)
            subtitle_font = ImageFont.truetype(FONT_REGULAR, subtitle_font_size)
            subtitle_bbox = draw.textbbox((0,0), subtitle, font=subtitle_font)
            subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
            subtitle_height = subtitle_bbox[3] - subtitle_bbox[1]
            subtitle_x = (text_area_width - subtitle_width) / 2
            subtitle_y = title_y + title_height + 20
            draw.text((subtitle_x, subtitle_y), subtitle, font=subtitle_font, fill=WHITE, align="center")

    elif style == "number":
        # Big number/stat with subtitle
        # Title (the number)
        max_title_width = int(WIDTH * 0.4)
        max_title_height = int(HEIGHT * 0.6)
        title_font_size = get_font_size(title, FONT_BLACK, max_title_width, max_title_height, draw)
        title_font = ImageFont.truetype(FONT_BLACK, title_font_size)
        title_bbox = draw.textbbox((0,0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]
        title_x = (WIDTH - title_width) / 2
        title_y = (HEIGHT - title_height) / 2 - (title_height / 4)
        draw.text((title_x, title_y), title, font=title_font, fill=accent_color, align="center")

        # Subtitle
        if subtitle:
            max_subtitle_width = int(WIDTH * 0.8)
            max_subtitle_height = int(HEIGHT * 0.2)
            subtitle_font_size = get_font_size(subtitle, FONT_REGULAR, max_subtitle_width, max_subtitle_height, draw)
            subtitle_font = ImageFont.truetype(FONT_REGULAR, subtitle_font_size)
            subtitle_bbox = draw.textbbox((0,0), subtitle, font=subtitle_font)
            subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
            subtitle_height = subtitle_bbox[3] - subtitle_bbox[1]
            subtitle_x = (WIDTH - subtitle_width) / 2
            subtitle_y = title_y + title_height + 20
            draw.text((subtitle_x, subtitle_y), subtitle, font=subtitle_font, fill=WHITE, align="center")

    elif style == "vs":
        # Two products side-by-side with 'VS' in the middle
        # Left product title
        left_text_area_width = int(WIDTH * 0.4)
        max_title_height = int(HEIGHT * 0.6)
        title1_font_size = get_font_size(title, FONT_BLACK, left_text_area_width, max_title_height, draw)
        title1_font = ImageFont.truetype(FONT_BLACK, title1_font_size)
        title1_bbox = draw.textbbox((0,0), title, font=title1_font)
        title1_width = title1_bbox[2] - title1_bbox[0]
        title1_height = title1_bbox[3] - title1_bbox[1]
        title1_x = (left_text_area_width - title1_width) / 2
        title1_y = (HEIGHT - title1_height) / 2
        draw.text((title1_x, title1_y), title, font=title1_font, fill=WHITE, align="center")

        # 'VS' text
        vs_font_size = get_font_size("VS", FONT_BLACK, int(WIDTH * 0.15), int(HEIGHT * 0.3), draw)
        vs_font = ImageFont.truetype(FONT_BLACK, vs_font_size)
        vs_bbox = draw.textbbox((0,0), "VS", font=vs_font)
        vs_width = vs_bbox[2] - vs_bbox[0]
        vs_height = vs_bbox[3] - vs_bbox[1]
        vs_x = (WIDTH - vs_width) / 2
        vs_y = (HEIGHT - vs_height) / 2
        draw.text((vs_x, vs_y), "VS", font=vs_font, fill=accent_color, align="center")

        # Right product title (using subtitle for second product)
        right_text_area_width = int(WIDTH * 0.4)
        title2_font_size = get_font_size(subtitle, FONT_BLACK, right_text_area_width, max_title_height, draw)
        title2_font = ImageFont.truetype(FONT_BLACK, title2_font_size)
        title2_bbox = draw.textbbox((0,0), subtitle, font=title2_font)
        title2_width = title2_bbox[2] - title2_bbox[0]
        title2_height = title2_bbox[3] - title2_bbox[1]
        title2_x = WIDTH - right_text_area_width + (right_text_area_width - title2_width) / 2
        title2_y = (HEIGHT - title2_height) / 2
        draw.text((title2_x, title2_y), subtitle, font=title2_font, fill=WHITE, align="center")

    elif style == "list":
        # Numbered items
        # The 'title' will be the main list title, and 'subtitle' will be a comma-separated string of list items
        list_items = subtitle.split(',')
        y_offset = int(HEIGHT * 0.1)
        line_height = int(HEIGHT * 0.1)

        # Main list title
        max_title_width = int(WIDTH * 0.9)
        max_title_height = int(HEIGHT * 0.2)
        title_font_size = get_font_size(title, FONT_BLACK, max_title_width, max_title_height, draw)
        title_font = ImageFont.truetype(FONT_BLACK, title_font_size)
        title_bbox = draw.textbbox((0,0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (WIDTH - title_width) / 2
        draw.text((title_x, y_offset), title, font=title_font, fill=accent_color, align="center")
        y_offset += title_bbox[3] - title_bbox[1] + 30

        # List items
        for i, item in enumerate(list_items):
            display_text = f"{i+1}. {item.strip()}"
            max_item_width = int(WIDTH * 0.8)
            max_item_height = int(line_height * 0.8)
            item_font_size = get_font_size(display_text, FONT_REGULAR, max_item_width, max_item_height, draw)
            item_font = ImageFont.truetype(FONT_REGULAR, item_font_size)
            item_bbox = draw.textbbox((0,0), display_text, font=item_font)
            item_width = item_bbox[2] - item_bbox[0]
            item_x = (WIDTH - item_width) / 2
            draw.text((item_x, y_offset), display_text, font=item_font, fill=WHITE, align="left")
            y_offset += line_height

    # All styles implemented

    if output_path:
        img.save(output_path)
        return None
    else:
        return img

def add_badge(image, badge_text, position="top_right", color=DARK_PINK):
    draw = ImageDraw.Draw(image)
    badge_font_size = 1
    badge_font = ImageFont.truetype(FONT_BOLD, badge_font_size)
    # Determine initial font size for badge
    while draw.textbbox((0,0), badge_text, font=badge_font)[2] < image.width / 5 and badge_font_size < 100:
        badge_font_size += 1
        badge_font = ImageFont.truetype(FONT_BOLD, badge_font_size)
    badge_font_size -= 1 # Go back one size to ensure it fits
    badge_font = ImageFont.truetype(FONT_BOLD, badge_font_size)

    badge_bbox = draw.textbbox((0,0), badge_text, font=badge_font)
    badge_width = badge_bbox[2] - badge_bbox[0]
    badge_height = badge_bbox[3] - badge_bbox[1]

    padding = 20
    margin = 30

    # Calculate badge position
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
        x, y = margin, margin # Default to top_left

    # Draw badge background (slightly larger than text)
    draw.rectangle([(x - padding, y - padding), (x + badge_width + padding, y + badge_height + padding)], fill=color)
    draw.text((x, y), badge_text, font=badge_font, fill=WHITE)

    return image

def generate_thumbnail_set(product_name, hook_type, content_style, keywords=None):
    variants = {}
    style_label = human_style_name(content_style)

    # Variant A: Bold Text Style
    variants["variant_a"] = generate_thumbnail(
        title=f"{product_name.upper()} REVIEW",
        subtitle=f"The {hook_type} you need!",
        style="bold_text",
        accent_color=DARK_PINK
    )

    # Variant B: Split Style
    variants["variant_b"] = generate_thumbnail(
        title=f"IS {product_name.upper()} WORTH IT?",
        subtitle=f"Unbiased {style_label}",
        style="split",
        accent_color=DARK_PINK
    )

    # Variant C: Number Style (if keywords provided, use first as a number/stat)
    if keywords and len(keywords) > 0:
        variants["variant_c"] = generate_thumbnail(
            title=f"{keywords[0].upper()}",
            subtitle=f"{product_name} {style_label}",
            style="number",
            accent_color=DARK_PINK
        )
    else:
        variants["variant_c"] = generate_thumbnail(
            title=f"TOP {product_name.upper()}",
            subtitle=f"Why it's the best {style_label}",
            style="bold_text",
            accent_color=DARK_PINK
        )

    return variants


# Main test block
if __name__ == "__main__":
    # Ensure assets directory exists for the test
    if not os.path.exists(ASSETS_DIR):
        os.makedirs(ASSETS_DIR)

    # Create dummy font files for testing if they don't exist
    # In a real scenario, these would be provided.
    # For now, we'll just make sure the paths are valid for ImageFont.truetype
    # This part is just to prevent errors during initial testing if fonts aren't copied yet.
    # The actual font files are expected to be in the assets directory.
    for font_file in [FONT_BOLD, FONT_BLACK, FONT_REGULAR]:
        if not os.path.exists(font_file):
            # Create a dummy file or link to a system font if possible for testing
            # For now, we assume the mv command in setup phase was successful.
            pass

    print("Generating sample thumbnails...")

    # Sample 1: Bold Text Style
    generate_thumbnail(
        title="THE BEST SMARTPHONE OF 2024",
        style="bold_text",
        output_path="sample_bold_text.png"
    )
    print("Generated sample_bold_text.png")

    # Sample 2: Bold Text Style with a different accent color
    generate_thumbnail(
        title="TOP 5 GAMING LAPTOPS",
        accent_color=(0, 150, 255), # Blue accent
        style="bold_text",
        output_path="sample_bold_text_blue.png"
    )
    print("Generated sample_bold_text_blue.png")

    # Sample 3: Split Style
    generate_thumbnail(
        title="ULTIMATE GUIDE",
        subtitle="To Smart Home Devices",
        style="split",
        output_path="sample_split.png"
    )
    print("Generated sample_split.png")

    # Sample 4: Number Style
    generate_thumbnail(
        title="10X",
        subtitle="Your Productivity Today!",
        style="number",
        output_path="sample_number.png"
    )
    print("Generated sample_number.png")

    # Sample 5: VS Style
    generate_thumbnail(
        title="iPhone 15 Pro",
        subtitle="Galaxy S24 Ultra",
        style="vs",
        output_path="sample_vs.png"
    )
    print("Generated sample_vs.png")

    # Sample 6: List Style
    generate_thumbnail(
        title="TOP 5 FEATURES",
        subtitle="Fast Charging, Long Battery Life, AI Camera, Foldable Screen, Gaming Performance",
        style="list",
        output_path="sample_list.png"
    )
    print("Generated sample_list.png")

    # Sample 7: Add badge to an existing thumbnail
    badge_test_img = generate_thumbnail(
        title="LIMITED TIME OFFER",
        style="bold_text",
        output_path=None
    )
    badge_test_img_with_badge = add_badge(badge_test_img, "NEW", position="top_right")
    badge_test_img_with_badge.save("sample_badge_new.png")
    print("Generated sample_badge_new.png")

    badge_test_img_with_badge_2 = add_badge(badge_test_img, "TOP PICK", position="bottom_left", color=(255, 165, 0)) # Orange badge
    badge_test_img_with_badge_2.save("sample_badge_top_pick.png")
    print("Generated sample_badge_top_pick.png")

    # Sample 8: Generate a thumbnail set
    product = "Wireless Earbuds"
    hook = "Game Changer"
    content = "In-depth"
    keywords = ["99", "Sound Quality", "Battery Life"]
    thumbnail_set = generate_thumbnail_set(product, hook, content, keywords)

    for variant_name, img_obj in thumbnail_set.items():
        output_filename = f"sample_set_{variant_name}.png"
        img_obj.save(output_filename)
        print(f"Generated {output_filename}")

    print("Thumbnail generation complete.")
