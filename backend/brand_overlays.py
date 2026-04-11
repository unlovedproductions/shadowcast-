
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

# Brand Colors
BG_COLOR = (10, 10, 15)  # Near black
ACCENT_COLOR = (196, 80, 122)  # Dark pink #c4507a
TEXT_COLOR = (255, 255, 255)  # White

# Asset Paths
ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
FONT_DIR = ASSET_DIR
LOGO_PATH = os.path.join(ASSET_DIR, "logo.png")
MONTSERRAT_BOLD = os.path.join(FONT_DIR, "Montserrat-Bold.ttf")
MONTSERRAT_BLACK = os.path.join(FONT_DIR, "Montserrat-Black.ttf")
MONTSERRAT_REGULAR = os.path.join(FONT_DIR, "Montserrat-Regular.ttf")

NOTO_SANS_BOLD = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
NOTO_SANS_BLACK = "/usr/share/fonts/truetype/noto/NotoSans-Black.ttf"
NOTO_SANS_REGULAR = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"

def load_font(font_path, fallback_path, size):
    """Loads a font, with a fallback if the primary font is not found."""
    try:
        return ImageFont.truetype(font_path, size)
    except IOError:
        try:
            return ImageFont.truetype(fallback_path, size)
        except IOError:
            print(f"Warning: Could not load font from {font_path} or {fallback_path}. Using default PIL font.")
            return ImageFont.load_default()

# Helper to convert PIL Image to numpy array
def pil_to_numpy(img):
    return np.array(img)

# Helper to convert numpy array to PIL Image
def numpy_to_pil(arr):
    return Image.fromarray(arr)

# --- Branded Visual Package Functions ---

def _load_logo(max_size):
    """Load the Unloved Productions logo, resized to fit max_size.
    Converts white/near-white background pixels to transparent so the logo
    blends cleanly onto dark intro/outro frames.
    """
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert('RGBA')
            # Remove white/near-white background pixels (R>200, G>200, B>200)
            logo_data = np.array(logo)
            r, g, b, a = logo_data[:,:,0], logo_data[:,:,1], logo_data[:,:,2], logo_data[:,:,3]
            white_mask = (r > 200) & (g > 200) & (b > 200)
            logo_data[white_mask, 3] = 0  # Set alpha to 0 for white pixels
            logo = Image.fromarray(logo_data, 'RGBA')
            logo.thumbnail((max_size, max_size), Image.LANCZOS)
            return logo
        except Exception as e:
            print(f"Warning: Could not load logo: {e}")
    return None


def render_branded_intro(width, height, series_name="", product_name=""):
    """Returns numpy array frame for branded intro. Shows Unloved Productions logo + ShadowCast text with dark pink glow on black."""
    img = Image.new('RGBA', (width, height), BG_COLOR + (255,))
    draw = ImageDraw.Draw(img)

    # Load and place the company logo at top center
    logo_size = int(height * 0.30)
    logo = _load_logo(logo_size)
    logo_bottom_y = int(height * 0.08)  # top margin
    if logo:
        logo_x = (width - logo.width) // 2
        logo_y = logo_bottom_y
        img.paste(logo, (logo_x, logo_y), logo)
        logo_bottom_y = logo_y + logo.height + int(height * 0.02)
    else:
        logo_bottom_y = int(height * 0.15)

    # ShadowCast Text below logo — scale to fit within 80% of frame width
    sc_font_size = int(height * 0.10)
    sc_font = load_font(MONTSERRAT_BLACK, NOTO_SANS_BLACK, sc_font_size)
    sc_text = "ShadowCast"
    sc_text_bbox = draw.textbbox((0, 0), sc_text, font=sc_font)
    sc_text_width = sc_text_bbox[2] - sc_text_bbox[0]
    max_text_width = int(width * 0.8)
    while sc_text_width > max_text_width and sc_font_size > 20:
        sc_font_size -= 4
        sc_font = load_font(MONTSERRAT_BLACK, NOTO_SANS_BLACK, sc_font_size)
        sc_text_bbox = draw.textbbox((0, 0), sc_text, font=sc_font)
        sc_text_width = sc_text_bbox[2] - sc_text_bbox[0]
    sc_text_height = sc_text_bbox[3] - sc_text_bbox[1]
    sc_text_x = (width - sc_text_width) / 2
    sc_text_y = logo_bottom_y

    # Glow effect (multiple layers of blurred text)
    glow_color = ACCENT_COLOR + (150,)
    for i in range(10, 0, -1):
        glow_img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_img)
        glow_draw.text((sc_text_x, sc_text_y), sc_text, font=sc_font, fill=glow_color)
        glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=i))
        img = Image.alpha_composite(img, glow_img)

    # Main ShadowCast text
    draw = ImageDraw.Draw(img)
    draw.text((sc_text_x, sc_text_y), sc_text, font=sc_font, fill=TEXT_COLOR)

    # Series Name / Product Name below ShadowCast — scale to fit
    if series_name or product_name:
        sub_font_size = int(height * 0.04)
        sub_font = load_font(MONTSERRAT_REGULAR, NOTO_SANS_REGULAR, sub_font_size)
        sub_text = f"{series_name} - {product_name}" if series_name and product_name else series_name or product_name
        sub_text_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
        sub_text_width = sub_text_bbox[2] - sub_text_bbox[0]
        max_sub_width = int(width * 0.85)
        while sub_text_width > max_sub_width and sub_font_size > 14:
            sub_font_size -= 2
            sub_font = load_font(MONTSERRAT_REGULAR, NOTO_SANS_REGULAR, sub_font_size)
            sub_text_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
            sub_text_width = sub_text_bbox[2] - sub_text_bbox[0]
        sub_text_x = (width - sub_text_width) / 2
        sub_text_y = sc_text_y + sc_text_height + int(height * 0.02)
        draw.text((sub_text_x, sub_text_y), sub_text, font=sub_font, fill=TEXT_COLOR)

    # Motto at bottom
    motto_font_size = int(height * 0.03)
    motto_font = load_font(MONTSERRAT_REGULAR, NOTO_SANS_REGULAR, motto_font_size)
    motto_text = "Forged in Passion"
    motto_text_bbox = draw.textbbox((0, 0), motto_text, font=motto_font)
    motto_text_width = motto_text_bbox[2] - motto_text_bbox[0]
    motto_text_x = (width - motto_text_width) / 2
    motto_text_y = height - int(height * 0.05) - motto_text_bbox[3]
    draw.text((motto_text_x, motto_text_y), motto_text, font=motto_font, fill=ACCENT_COLOR)

    return pil_to_numpy(img.convert('RGB'))

def render_branded_outro(width, height):
    """Returns numpy array frame for branded outro. Shows logo + 'Subscribe for more honest reviews' + 'ShadowCast' branding."""
    img = Image.new('RGBA', (width, height), BG_COLOR + (255,))
    draw = ImageDraw.Draw(img)

    # Logo at top
    logo_size = int(height * 0.20)
    logo = _load_logo(logo_size)
    content_start_y = int(height * 0.08)
    if logo:
        logo_x = (width - logo.width) // 2
        img.paste(logo, (logo_x, content_start_y), logo)
        content_start_y = content_start_y + logo.height + int(height * 0.03)
    else:
        content_start_y = int(height * 0.15)

    draw = ImageDraw.Draw(img)

    # Subscribe Text — scale to fit within 80% of frame width
    sub_msg_font_size = int(height * 0.07)
    sub_msg_font = load_font(MONTSERRAT_BOLD, NOTO_SANS_BOLD, sub_msg_font_size)
    sub_msg_text = "Subscribe for more honest reviews"
    sub_msg_text_bbox = draw.textbbox((0, 0), sub_msg_text, font=sub_msg_font)
    sub_msg_text_width = sub_msg_text_bbox[2] - sub_msg_text_bbox[0]
    max_text_width = int(width * 0.8)
    while sub_msg_text_width > max_text_width and sub_msg_font_size > 16:
        sub_msg_font_size -= 4
        sub_msg_font = load_font(MONTSERRAT_BOLD, NOTO_SANS_BOLD, sub_msg_font_size)
        sub_msg_text_bbox = draw.textbbox((0, 0), sub_msg_text, font=sub_msg_font)
        sub_msg_text_width = sub_msg_text_bbox[2] - sub_msg_text_bbox[0]
    sub_msg_text_height = sub_msg_text_bbox[3] - sub_msg_text_bbox[1]
    sub_msg_x = (width - sub_msg_text_width) / 2
    sub_msg_y = content_start_y
    draw.text((sub_msg_x, sub_msg_y), sub_msg_text, font=sub_msg_font, fill=TEXT_COLOR)

    # ShadowCast Branding — scale to fit within 80% of frame width
    sc_font_size = int(height * 0.10)
    sc_font = load_font(MONTSERRAT_BLACK, NOTO_SANS_BLACK, sc_font_size)
    sc_text = "ShadowCast"
    sc_text_bbox = draw.textbbox((0, 0), sc_text, font=sc_font)
    sc_text_width = sc_text_bbox[2] - sc_text_bbox[0]
    while sc_text_width > max_text_width and sc_font_size > 20:
        sc_font_size -= 4
        sc_font = load_font(MONTSERRAT_BLACK, NOTO_SANS_BLACK, sc_font_size)
        sc_text_bbox = draw.textbbox((0, 0), sc_text, font=sc_font)
        sc_text_width = sc_text_bbox[2] - sc_text_bbox[0]
    sc_text_height = sc_text_bbox[3] - sc_text_bbox[1]
    sc_text_x = (width - sc_text_width) / 2
    sc_text_y = sub_msg_y + sub_msg_text_height + int(height * 0.05)
    draw.text((sc_text_x, sc_text_y), sc_text, font=sc_font, fill=ACCENT_COLOR)

    # Unloved Productions
    prod_font_size = int(height * 0.03)
    prod_font = load_font(MONTSERRAT_REGULAR, NOTO_SANS_REGULAR, prod_font_size)
    prod_text = "by Unloved Productions"
    prod_text_bbox = draw.textbbox((0, 0), prod_text, font=prod_font)
    prod_text_width = prod_text_bbox[2] - prod_text_bbox[0]
    prod_text_x = (width - prod_text_width) / 2
    prod_text_y = sc_text_y + sc_text_height + int(height * 0.01)
    draw.text((prod_text_x, prod_text_y), prod_text, font=prod_font, fill=TEXT_COLOR)

    # Motto at bottom
    motto_font_size = int(height * 0.025)
    motto_font = load_font(MONTSERRAT_REGULAR, NOTO_SANS_REGULAR, motto_font_size)
    motto_text = "Forged in Passion"
    motto_text_bbox = draw.textbbox((0, 0), motto_text, font=motto_font)
    motto_text_width = motto_text_bbox[2] - motto_text_bbox[0]
    motto_text_x = (width - motto_text_width) / 2
    motto_text_y = height - int(height * 0.05) - motto_text_bbox[3]
    draw.text((motto_text_x, motto_text_y), motto_text, font=motto_font, fill=ACCENT_COLOR)

    return pil_to_numpy(img.convert('RGB'))

def render_watermark_overlay(width, height):
    """Returns RGBA PIL Image with semi-transparent 'SC' watermark in bottom-right corner."""
    watermark_img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark_img)

    wm_font_size = int(height * 0.1)
    wm_font = load_font(MONTSERRAT_BLACK, NOTO_SANS_BLACK, wm_font_size)
    wm_text = "SC"

    wm_text_bbox = draw.textbbox((0, 0), wm_text, font=wm_font)
    wm_text_width = wm_text_bbox[2] - wm_text_bbox[0]
    wm_text_height = wm_text_bbox[3] - wm_text_bbox[1]

    padding = int(width * 0.02)
    wm_x = width - wm_text_width - padding
    wm_y = height - wm_text_height - padding

    # Semi-transparent accent color
    wm_color = ACCENT_COLOR + (100,) # 100 alpha for semi-transparency
    draw.text((wm_x, wm_y), wm_text, font=wm_font, fill=wm_color)

    return watermark_img

def render_lower_third(width, height, product_name, price="", is_short_form=False):
    """Returns RGBA PIL Image with persistent lower-third bar showing product name and price with dark pink accent line."""
    lt_height = int(height * 0.12) if is_short_form else int(height * 0.08)
    lt_img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(lt_img)

    # Background bar
    bar_color = BG_COLOR + (200,) # Semi-transparent background
    draw.rectangle([(0, height - lt_height), (width, height)], fill=bar_color)

    # Accent line
    accent_line_height = int(lt_height * 0.1)
    draw.rectangle([(0, height - lt_height), (width, height - lt_height + accent_line_height)], fill=ACCENT_COLOR)

    # Text content
    text_padding_x = int(width * 0.02)
    text_padding_y = int(lt_height * 0.2)

    # Product Name
    prod_name_font_size = int(lt_height * 0.4)
    prod_name_font = load_font(MONTSERRAT_BOLD, NOTO_SANS_BOLD, prod_name_font_size)

    # Price (if provided) — measure price first so we can reserve space on the right
    price_reserved_width = 0
    price_font = None
    price_text_width = 0
    price_text_height = 0
    if price:
        price_font_size = int(lt_height * 0.35)
        price_font = load_font(MONTSERRAT_REGULAR, NOTO_SANS_REGULAR, price_font_size)
        price_text_bbox = draw.textbbox((0, 0), price, font=price_font)
        price_text_width = price_text_bbox[2] - price_text_bbox[0]
        price_text_height = price_text_bbox[3] - price_text_bbox[1]
        price_reserved_width = price_text_width + text_padding_x * 3  # gap between name and price

    # Truncate product name with ellipsis if it would overlap the price area
    max_prod_name_width = width - text_padding_x - price_reserved_width - text_padding_x
    display_name = product_name
    prod_name_text_bbox = draw.textbbox((0, 0), display_name, font=prod_name_font)
    prod_name_text_width = prod_name_text_bbox[2] - prod_name_text_bbox[0]
    if prod_name_text_width > max_prod_name_width:
        # Truncate character by character until it fits
        while len(display_name) > 1:
            display_name = display_name[:-1]
            test_bbox = draw.textbbox((0, 0), display_name + "...", font=prod_name_font)
            if (test_bbox[2] - test_bbox[0]) <= max_prod_name_width:
                display_name = display_name + "..."
                break
        prod_name_text_bbox = draw.textbbox((0, 0), display_name, font=prod_name_font)

    prod_name_text_height = prod_name_text_bbox[3] - prod_name_text_bbox[1]
    prod_name_y = height - lt_height + accent_line_height + (lt_height - accent_line_height - prod_name_text_height) / 2
    draw.text((text_padding_x, prod_name_y), display_name, font=prod_name_font, fill=TEXT_COLOR)

    # Draw price on the right side
    if price and price_font is not None:
        price_x = width - price_text_width - text_padding_x
        price_y = height - lt_height + accent_line_height + (lt_height - accent_line_height - price_text_height) / 2
        draw.text((price_x, price_y), price, font=price_font, fill=TEXT_COLOR)

    return lt_img

# --- Progress/Context Overlays Functions ---

def render_progress_overlay(width, height, progress_fraction, chapter_text="", item_text="", accent_color=ACCENT_COLOR):
    """Returns RGBA PIL Image. Shows a thin progress bar at bottom + optional 'Chapter: X' in top-left + optional 'Product 3 of 5' in top-right."""
    overlay_img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay_img)

    # Progress Bar at bottom
    bar_height = int(height * 0.01)
    draw.rectangle([(0, height - bar_height), (width * progress_fraction, height)], fill=accent_color)

    # Text elements
    text_font_size = int(height * 0.035)
    text_font = load_font(MONTSERRAT_REGULAR, NOTO_SANS_REGULAR, text_font_size)
    padding = int(width * 0.02)

    if chapter_text:
        draw.text((padding, padding), chapter_text, font=text_font, fill=TEXT_COLOR)

    if item_text:
        item_text_bbox = draw.textbbox((0, 0), item_text, font=text_font)
        item_text_width = item_text_bbox[2] - item_text_bbox[0]
        draw.text((width - item_text_width - padding, padding), item_text, font=text_font, fill=TEXT_COLOR)

    return overlay_img

def render_section_header(width, height, section_type, accent_color=ACCENT_COLOR):
    """Returns RGBA PIL Image. section_type is 'pros', 'cons', 'verdict', 'comparison'. Shows a styled header banner."""
    header_img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(header_img)

    header_height = int(height * 0.1)
    text_font_size = int(header_height * 0.5)
    text_font = load_font(MONTSERRAT_BOLD, NOTO_SANS_BOLD, text_font_size)
    padding_x = int(width * 0.03)

    text_map = {
        "pros": ("✓ THE GOOD", (0, 150, 0)),  # Green
        "cons": ("✗ THE BAD", (150, 0, 0)),  # Red
        "verdict": ("★ VERDICT", accent_color), # Accent
        "comparison": ("↔ COMPARISON", (0, 100, 150)) # Blue-ish
    }

    display_text, section_color = text_map.get(section_type.lower(), ("SECTION", (100, 100, 100)))

    # Background bar
    bar_color = section_color + (200,) # Semi-transparent
    draw.rectangle([(0, 0), (width, header_height)], fill=bar_color)

    # Text
    text_bbox = draw.textbbox((0, 0), display_text, font=text_font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_y = (header_height - text_height) / 2
    draw.text((padding_x, text_y), display_text, font=text_font, fill=TEXT_COLOR)

    return header_img

# --- Engagement Bait Moments Functions ---

def render_poll_card(width, height, question, option_a, option_b, accent_color=ACCENT_COLOR):
    """Returns numpy array frame. Shows a poll-style visual with two options side by side."""
    img = Image.new('RGB', (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    card_width = int(width * 0.8)
    card_height = int(height * 0.6)
    card_x = (width - card_width) / 2
    card_y = (height - card_height) / 2

    # Card background
    draw.rounded_rectangle([(card_x, card_y), (card_x + card_width, card_y + card_height)], radius=20, fill=(20, 20, 30))

    # Question
    q_font_size = int(card_height * 0.1)
    q_font = load_font(MONTSERRAT_BOLD, NOTO_SANS_BOLD, q_font_size)
    q_text_bbox = draw.textbbox((0, 0), question, font=q_font)
    q_text_width = q_text_bbox[2] - q_text_bbox[0]
    q_text_height = q_text_bbox[3] - q_text_bbox[1]
    q_x = card_x + (card_width - q_text_width) / 2
    q_y = card_y + int(card_height * 0.1)
    draw.text((q_x, q_y), question, font=q_font, fill=TEXT_COLOR)

    # Options
    opt_font_size = int(card_height * 0.12)
    opt_font = load_font(MONTSERRAT_BLACK, NOTO_SANS_BLACK, opt_font_size)
    opt_padding = int(card_width * 0.05)

    # Option A
    opt_a_text_bbox = draw.textbbox((0, 0), option_a, font=opt_font)
    opt_a_text_width = opt_a_text_bbox[2] - opt_a_text_bbox[0]
    opt_a_text_height = opt_a_text_bbox[3] - opt_a_text_bbox[1]
    opt_a_x = card_x + opt_padding + (card_width / 2 - opt_padding * 2 - opt_a_text_width) / 2
    opt_a_y = card_y + card_height * 0.55 - opt_a_text_height / 2
    draw.text((opt_a_x, opt_a_y), option_a, font=opt_font, fill=ACCENT_COLOR)

    # Option B
    opt_b_text_bbox = draw.textbbox((0, 0), option_b, font=opt_font)
    opt_b_text_width = opt_b_text_bbox[2] - opt_b_text_bbox[0]
    opt_b_text_height = opt_b_text_bbox[3] - opt_b_text_bbox[1]
    opt_b_x = card_x + card_width / 2 + opt_padding + (card_width / 2 - opt_padding * 2 - opt_b_text_width) / 2
    opt_b_y = card_y + card_height * 0.55 - opt_b_text_height / 2
    draw.text((opt_b_x, opt_b_y), option_b, font=opt_font, fill=TEXT_COLOR)

    # Separator line
    draw.line([(card_x + card_width / 2, card_y + card_height * 0.4), (card_x + card_width / 2, card_y + card_height * 0.8)], fill=TEXT_COLOR, width=3)

    return pil_to_numpy(img)

def render_comment_prompt(width, height, question, accent_color=ACCENT_COLOR):
    """Returns numpy array frame. Shows a distinct 'comment prompt' card with animated-looking border and question."""
    img = Image.new('RGB', (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    card_width = int(width * 0.7)
    card_height = int(height * 0.4)
    card_x = (width - card_width) / 2
    card_y = (height - card_height) / 2

    # Animated border effect (simplified: just a thicker accent border)
    border_thickness = 10
    draw.rounded_rectangle([(card_x - border_thickness, card_y - border_thickness), 
                            (card_x + card_width + border_thickness, card_y + card_height + border_thickness)], 
                           radius=30, fill=accent_color)
    draw.rounded_rectangle([(card_x, card_y), (card_x + card_width, card_y + card_height)], radius=20, fill=(20, 20, 30))

    # Question text
    q_font_size = int(card_height * 0.15)
    q_font = load_font(MONTSERRAT_BOLD, NOTO_SANS_BOLD, q_font_size)
    
    # Wrap text if too long
    lines = []
    current_line = []
    words = question.split()
    for word in words:
        test_line = " ".join(current_line + [word])
        test_bbox = draw.textbbox((0, 0), test_line, font=q_font)
        test_width = test_bbox[2] - test_bbox[0]
        if test_width < card_width * 0.8:
            current_line.append(word)
        else:
            lines.append(" ".join(current_line))
            current_line = [word]
    lines.append(" ".join(current_line))
    
    wrapped_question = "\n".join(lines)

    q_text_bbox = draw.textbbox((0, 0), wrapped_question, font=q_font)
    q_text_width = q_text_bbox[2] - q_text_bbox[0]
    q_text_height = q_text_bbox[3] - q_text_bbox[1]
    q_x = card_x + (card_width - q_text_width) / 2
    q_y = card_y + (card_height - q_text_height) / 2
    draw.text((q_x, q_y), wrapped_question, font=q_font, fill=TEXT_COLOR, align="center")

    return pil_to_numpy(img)

def render_subscribe_card(width, height, accent_color=ACCENT_COLOR):
    """Returns numpy array frame. Branded subscribe reminder."""
    img = Image.new('RGB', (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    card_width = int(width * 0.7)
    card_height = int(height * 0.5)
    card_x = (width - card_width) / 2
    card_y = (height - card_height) / 2

    # Card background
    draw.rounded_rectangle([(card_x, card_y), (card_x + card_width, card_y + card_height)], radius=20, fill=(20, 20, 30))

    # Subscribe Icon (simplified as a circle)
    icon_radius = int(card_height * 0.1)
    icon_center_x = card_x + card_width / 2
    icon_center_y = card_y + int(card_height * 0.25)
    draw.ellipse([(icon_center_x - icon_radius, icon_center_y - icon_radius),
                  (icon_center_x + icon_radius, icon_center_y + icon_radius)], fill=accent_color)

    # Text: Subscribe
    sub_font_size = int(card_height * 0.15)
    sub_font = load_font(MONTSERRAT_BLACK, NOTO_SANS_BLACK, sub_font_size)
    sub_text = "SUBSCRIBE"
    sub_text_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
    sub_text_width = sub_text_bbox[2] - sub_text_bbox[0]
    sub_text_height = sub_text_bbox[3] - sub_text_bbox[1]
    sub_text_x = card_x + (card_width - sub_text_width) / 2
    sub_text_y = icon_center_y + icon_radius + int(card_height * 0.05)
    draw.text((sub_text_x, sub_text_y), sub_text, font=sub_font, fill=TEXT_COLOR)

    # Text: Don't miss out!
    tag_font_size = int(card_height * 0.08)
    tag_font = load_font(MONTSERRAT_REGULAR, NOTO_SANS_REGULAR, tag_font_size)
    tag_text = "Don't miss out on honest reviews!"
    tag_text_bbox = draw.textbbox((0, 0), tag_text, font=tag_font)
    tag_text_width = tag_text_bbox[2] - tag_text_bbox[0]
    tag_text_height = tag_text_bbox[3] - tag_text_bbox[1]
    tag_text_x = card_x + (card_width - tag_text_width) / 2
    tag_text_y = sub_text_y + sub_text_height + int(card_height * 0.02)
    draw.text((tag_text_x, tag_text_y), tag_text, font=tag_font, fill=TEXT_COLOR)

    return pil_to_numpy(img)


if __name__ == "__main__":
    # Create assets directory if it doesn't exist
    os.makedirs(FONT_DIR, exist_ok=True)
    os.makedirs("test_overlays", exist_ok=True)

    # Dummy font files for testing if not present
    # In a real scenario, these would be provided or installed.
    # For now, we'll rely on the fallback mechanism.
    # You might need to manually place Montserrat fonts in ./assets/ for best results.

    WIDTH, HEIGHT = 1920, 1080
    SHORT_WIDTH, SHORT_HEIGHT = 1080, 1920

    print("Generating test images...")

    # Branded Visual Package
    Image.fromarray(render_branded_intro(WIDTH, HEIGHT, "Product Review", "Awesome Gadget")).save("test_overlays/intro_long.png")
    Image.fromarray(render_branded_intro(SHORT_WIDTH, SHORT_HEIGHT, "Quick Take", "Tiny Widget")).save("test_overlays/intro_short.png")
    Image.fromarray(render_branded_outro(WIDTH, HEIGHT)).save("test_overlays/outro_long.png")
    Image.fromarray(render_branded_outro(SHORT_WIDTH, SHORT_HEIGHT)).save("test_overlays/outro_short.png")
    render_watermark_overlay(WIDTH, HEIGHT).save("test_overlays/watermark_long.png")
    render_watermark_overlay(SHORT_WIDTH, SHORT_HEIGHT).save("test_overlays/watermark_short.png")
    render_lower_third(WIDTH, HEIGHT, "Super Product X", "$99.99").save("test_overlays/lower_third_long.png")
    render_lower_third(SHORT_WIDTH, SHORT_HEIGHT, "Mini Product Y", "Free", is_short_form=True).save("test_overlays/lower_third_short.png")

    # Progress/Context Overlays
    render_progress_overlay(WIDTH, HEIGHT, 0.5, "Chapter: Design", "Item 3 of 5").save("test_overlays/progress_long.png")
    render_progress_overlay(SHORT_WIDTH, SHORT_HEIGHT, 0.75, "Part 2", "Product 1 of 3").save("test_overlays/progress_short.png")
    render_section_header(WIDTH, HEIGHT, "pros").save("test_overlays/header_pros_long.png")
    render_section_header(WIDTH, HEIGHT, "cons").save("test_overlays/header_cons_long.png")
    render_section_header(WIDTH, HEIGHT, "verdict").save("test_overlays/header_verdict_long.png")
    render_section_header(SHORT_WIDTH, SHORT_HEIGHT, "comparison").save("test_overlays/header_comparison_short.png")

    # Engagement Bait Moments
    Image.fromarray(render_poll_card(WIDTH, HEIGHT, "Which is better?", "Option A", "Option B")).save("test_overlays/poll_long.png")
    Image.fromarray(render_poll_card(SHORT_WIDTH, SHORT_HEIGHT, "Coffee or Tea?", "Coffee", "Tea")).save("test_overlays/poll_short.png")
    Image.fromarray(render_comment_prompt(WIDTH, HEIGHT, "What's your favorite feature of this product?")).save("test_overlays/comment_long.png")
    Image.fromarray(render_comment_prompt(SHORT_WIDTH, SHORT_HEIGHT, "Tell us your thoughts on the new update!")).save("test_overlays/comment_short.png")
    Image.fromarray(render_subscribe_card(WIDTH, HEIGHT)).save("test_overlays/subscribe_long.png")
    Image.fromarray(render_subscribe_card(SHORT_WIDTH, SHORT_HEIGHT)).save("test_overlays/subscribe_short.png")

    print("All test images generated in 'test_overlays/' directory.")
