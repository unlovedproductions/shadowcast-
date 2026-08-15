import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Brand colors
DARK_PINK = (196, 80, 122)
NEAR_BLACK = (10, 10, 15)
WHITE = (255, 255, 255)

# Font paths
import os as _os
_ASSETS_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "assets")
FONT_BOLD = _os.path.join(_ASSETS_DIR, "Montserrat-Bold.ttf")
FONT_BLACK = _os.path.join(_ASSETS_DIR, "Montserrat-Black.ttf")
FONT_REGULAR = _os.path.join(_ASSETS_DIR, "Montserrat-Regular.ttf")
FONT_EXTRABOLD = _os.path.join(_ASSETS_DIR, "Montserrat-ExtraBold.ttf")
FALLBACK_FONT = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"

def get_font(font_path, size):
    try:
        return ImageFont.truetype(font_path, size)
    except IOError:
        print(f"Warning: Font not found at {font_path}. Using fallback font.")
        return ImageFont.truetype(FALLBACK_FONT, size)


def render_vs_split_screen(width, height, product_a_name, product_b_name, accent_color=DARK_PINK):
    mid = width // 2
    ys = np.linspace(0.0, 1.0, height, endpoint=False, dtype=np.float32)[:, None]
    near = np.array(NEAR_BLACK, dtype=np.float32)
    left = np.clip(near * (1.0 - ys * 0.2), 0, 255).astype(np.uint8)
    right = np.clip(near * (1.0 - ys * -0.1), 0, 255).astype(np.uint8)
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:, :mid] = left
    canvas[:, mid:] = right
    img = Image.fromarray(canvas)
    draw = ImageDraw.Draw(img)

    # Vertical divider
    divider_width = 10
    draw.rectangle([(width // 2 - divider_width // 2, 0), (width // 2 + divider_width // 2, height)], fill=accent_color)

    # "VS" badge
    vs_font_size = int(height * 0.1)
    vs_font = get_font(FONT_BLACK, vs_font_size)
    vs_text = "VS"
    vs_bbox = draw.textbbox((0, 0), vs_text, font=vs_font)
    vs_width = vs_bbox[2] - vs_bbox[0]
    vs_height = vs_bbox[3] - vs_bbox[1]
    vs_x = width // 2 - vs_width // 2
    vs_y = height // 2 - vs_height // 2
    draw.text((vs_x, vs_y), vs_text, font=vs_font, fill=WHITE)

    # Product names
    product_font_size = int(height * 0.08)
    product_font = get_font(FONT_BOLD, product_font_size)

    # Product A name (left)
    product_a_bbox = draw.textbbox((0, 0), product_a_name, font=product_font)
    product_a_width = product_a_bbox[2] - product_a_bbox[0]
    product_a_x = (width // 2 - product_a_width) // 2
    product_a_y = height // 4 - (product_a_bbox[3] - product_a_bbox[1]) // 2
    draw.text((product_a_x, product_a_y), product_a_name, font=product_font, fill=WHITE)

    # Product B name (right)
    product_b_bbox = draw.textbbox((0, 0), product_b_name, font=product_font)
    product_b_width = product_b_bbox[2] - product_b_bbox[0]
    product_b_x = width // 2 + (width // 2 - product_b_width) // 2
    product_b_y = height // 4 - (product_b_bbox[3] - product_b_bbox[1]) // 2
    draw.text((product_b_x, product_b_y), product_b_name, font=product_font, fill=WHITE)

    return np.array(img)

def render_spec_comparison(width, height, spec_name, value_a, value_b, winner="a", accent_color=DARK_PINK):
    img = Image.new("RGB", (width, height), NEAR_BLACK)
    draw = ImageDraw.Draw(img)

    # Define font sizes
    spec_font_size = int(height * 0.2)
    value_font_size = int(height * 0.3)
    spec_font = get_font(FONT_BOLD, spec_font_size)
    value_font = get_font(FONT_REGULAR, value_font_size)

    # Spec name at the top
    spec_bbox = draw.textbbox((0, 0), spec_name, font=spec_font)
    spec_text_width = spec_bbox[2] - spec_bbox[0]
    spec_text_height = spec_bbox[3] - spec_bbox[1]
    draw.text(((width - spec_text_width) // 2, height * 0.1), spec_name, font=spec_font, fill=WHITE)

    # Value A (left)
    value_a_bbox = draw.textbbox((0, 0), value_a, font=value_font)
    value_a_width = value_a_bbox[2] - value_a_bbox[0]
    value_a_height = value_a_bbox[3] - value_a_bbox[1]
    value_a_x = (width // 2 - value_a_width) // 2
    value_a_y = height * 0.5 - value_a_height // 2

    # Value B (right)
    value_b_bbox = draw.textbbox((0, 0), value_b, font=value_font)
    value_b_width = value_b_bbox[2] - value_b_bbox[0]
    value_b_height = value_b_bbox[3] - value_b_bbox[1]
    value_b_x = width // 2 + (width // 2 - value_b_width) // 2
    value_b_y = height * 0.5 - value_b_height // 2

    # Highlight winner side
    border_thickness = int(width * 0.01)
    dim_color = (50, 50, 50) # A darker tone for the loser side

    if winner == "a":
        # Highlight left side
        draw.rectangle([(0, 0), (width // 2 - 1, height)], fill=NEAR_BLACK)
        draw.rectangle([(0, 0), (width // 2 - 1, height)], outline=accent_color, width=border_thickness)
        # Dim right side
        draw.rectangle([(width // 2 + 1, 0), (width, height)], fill=dim_color)
    elif winner == "b":
        # Highlight right side
        draw.rectangle([(width // 2 + 1, 0), (width, height)], fill=NEAR_BLACK)
        draw.rectangle([(width // 2 + 1, 0), (width, height)], outline=accent_color, width=border_thickness)
        # Dim left side
        draw.rectangle([(0, 0), (width // 2 - 1, height)], fill=dim_color)
    else:
        # No winner, no highlight
        draw.rectangle([(0, 0), (width // 2 - 1, height)], fill=NEAR_BLACK)
        draw.rectangle([(width // 2 + 1, 0), (width, height)], fill=NEAR_BLACK)

    # Redraw spec name and values to be on top of the background/highlight
    draw.text(((width - spec_text_width) // 2, height * 0.1), spec_name, font=spec_font, fill=WHITE)
    draw.text((value_a_x, value_a_y), value_a, font=value_font, fill=WHITE)
    draw.text((value_b_x, value_b_y), value_b, font=value_font, fill=WHITE)

    return np.array(img)

def render_scorecard(width, height, product_a_name, product_b_name, scores, accent_color=DARK_PINK):
    img = Image.new("RGB", (width, height), NEAR_BLACK)
    draw = ImageDraw.Draw(img)

    # Fonts
    title_font = get_font(FONT_BOLD, int(height * 0.05))
    header_font = get_font(FONT_BOLD, int(height * 0.04))
    category_font = get_font(FONT_REGULAR, int(height * 0.03))
    score_font = get_font(FONT_BOLD, int(height * 0.035))
    total_font = get_font(FONT_BLACK, int(height * 0.06))

    margin = int(width * 0.05)
    current_y = margin

    # Product names at the top
    product_a_bbox = draw.textbbox((0, 0), product_a_name, font=header_font)
    product_b_bbox = draw.textbbox((0, 0), product_b_name, font=header_font)

    product_a_x = margin
    product_b_x = width - margin - (product_b_bbox[2] - product_b_bbox[0])
    draw.text((product_a_x, current_y), product_a_name, font=header_font, fill=WHITE)
    draw.text((product_b_x, current_y), product_b_name, font=header_font, fill=WHITE)
    current_y += int(height * 0.07)

    # Divider below product names
    draw.line([(margin, current_y), (width - margin, current_y)], fill=WHITE, width=2)
    current_y += int(height * 0.02)

    total_score_a = 0
    total_score_b = 0

    # Render each score category
    for score_item in scores:
        category = score_item["category"]
        score_a = score_item["score_a"]
        score_b = score_item["score_b"]

        total_score_a += score_a
        total_score_b += score_b

        # Category name
        draw.text((margin, current_y), category, font=category_font, fill=WHITE)

        # Score bars and numbers
        bar_height = int(height * 0.015)
        bar_y = current_y + int(height * 0.005)
        bar_max_width = (width - 2 * margin) // 2 - int(width * 0.1)

        # Score A bar
        score_a_width = int((score_a / 10) * bar_max_width) # Assuming max score is 10
        draw.rectangle([(margin + bar_max_width - score_a_width, bar_y), (margin + bar_max_width, bar_y + bar_height)], fill=accent_color)
        draw.text((margin + bar_max_width + int(width * 0.01), current_y), str(score_a), font=score_font, fill=WHITE)

        # Score B bar
        score_b_width = int((score_b / 10) * bar_max_width) # Assuming max score is 10
        draw.rectangle([(width - margin - bar_max_width, bar_y), (width - margin - bar_max_width + score_b_width, bar_y + bar_height)], fill=accent_color)
        draw.text((width - margin - bar_max_width - int(width * 0.03) - int(width * 0.01), current_y), str(score_b), font=score_font, fill=WHITE)

        current_y += int(height * 0.06)

    # Divider before total scores
    current_y += int(height * 0.02)
    draw.line([(margin, current_y), (width - margin, current_y)], fill=WHITE, width=2)
    current_y += int(height * 0.02)

    # Total scores
    total_a_text = f"Total: {total_score_a}"
    total_b_text = f"Total: {total_score_b}"

    total_a_bbox = draw.textbbox((0, 0), total_a_text, font=total_font)
    total_b_bbox = draw.textbbox((0, 0), total_b_text, font=total_font)

    total_a_x = margin
    total_b_x = width - margin - (total_b_bbox[2] - total_b_bbox[0])

    if total_score_a > total_score_b:
        draw.text((total_a_x, current_y), total_a_text, font=total_font, fill=accent_color)
        draw.text((total_b_x, current_y), total_b_text, font=total_font, fill=WHITE)
    elif total_score_b > total_score_a:
        draw.text((total_a_x, current_y), total_a_text, font=total_font, fill=WHITE)
        draw.text((total_b_x, current_y), total_b_text, font=total_font, fill=accent_color)
    else:
        draw.text((total_a_x, current_y), total_a_text, font=total_font, fill=WHITE)
        draw.text((total_b_x, current_y), total_b_text, font=total_font, fill=WHITE)

    return np.array(img)

def render_price_comparison(width, height, products, accent_color=DARK_PINK):
    img = Image.new("RGB", (width, height), NEAR_BLACK)
    draw = ImageDraw.Draw(img)

    product_count = len(products)
    if product_count == 0:
        return np.array(img)

    # Fonts
    name_font = get_font(FONT_BOLD, int(height * 0.08))
    price_font = get_font(FONT_BLACK, int(height * 0.12))

    # Calculate spacing
    padding = int(width * 0.05)
    product_width = (width - padding * (product_count + 1)) // product_count
    current_x = padding

    for product in products:
        name = product["name"]
        price = product["price"]
        is_recommended = product.get("is_recommended", False)

        # Draw product box
        box_fill = NEAR_BLACK
        box_outline = WHITE
        outline_width = 2

        if is_recommended:
            box_outline = accent_color
            outline_width = 5

        draw.rectangle([(current_x, padding), (current_x + product_width, height - padding)],
                       fill=box_fill, outline=box_outline, width=outline_width)

        # Product name
        name_bbox = draw.textbbox((0, 0), name, font=name_font)
        name_text_width = name_bbox[2] - name_bbox[0]
        name_text_height = name_bbox[3] - name_bbox[1]
        name_x = current_x + (product_width - name_text_width) // 2
        name_y = padding + int(height * 0.1)
        draw.text((name_x, name_y), name, font=name_font, fill=WHITE)

        # Price
        price_bbox = draw.textbbox((0, 0), price, font=price_font)
        price_text_width = price_bbox[2] - price_bbox[0]
        price_text_height = price_bbox[3] - price_bbox[1]
        price_x = current_x + (product_width - price_text_width) // 2
        price_y = height // 2 - price_text_height // 2
        draw.text((price_x, price_y), price, font=price_font, fill=WHITE)

        if is_recommended:
            recommended_text = "Recommended"
            recommended_font = get_font(FONT_BOLD, int(height * 0.05))
            recommended_bbox = draw.textbbox((0, 0), recommended_text, font=recommended_font)
            recommended_text_width = recommended_bbox[2] - recommended_bbox[0]
            recommended_x = current_x + (product_width - recommended_text_width) // 2
            recommended_y = height - padding - int(height * 0.15)
            draw.text((recommended_x, recommended_y), recommended_text, font=recommended_font, fill=accent_color)

        current_x += product_width + padding

    return np.array(img)

def render_winner_reveal(width, height, winner_name, accent_color=DARK_PINK):
    img = Image.new("RGB", (width, height), NEAR_BLACK)
    draw = ImageDraw.Draw(img)

    # "WINNER" text
    winner_text = "WINNER"
    winner_font_size = int(height * 0.2)
    winner_font = get_font(FONT_BLACK, winner_font_size)

    # Calculate text position for centering
    winner_bbox = draw.textbbox((0, 0), winner_text, font=winner_font)
    winner_text_width = winner_bbox[2] - winner_bbox[0]
    winner_text_height = winner_bbox[3] - winner_bbox[1]
    winner_x = (width - winner_text_width) // 2
    winner_y = height // 3 - winner_text_height // 2

    # Accent glow (draw slightly larger text in accent color behind white text)
    glow_offset = int(width * 0.005)
    draw.text((winner_x - glow_offset, winner_y - glow_offset), winner_text, font=winner_font, fill=accent_color)
    draw.text((winner_x + glow_offset, winner_y + glow_offset), winner_text, font=winner_font, fill=accent_color)
    draw.text((winner_x, winner_y), winner_text, font=winner_font, fill=WHITE)

    # Winner product name
    name_font_size = int(height * 0.1)
    name_font = get_font(FONT_BOLD, name_font_size)

    name_bbox = draw.textbbox((0, 0), winner_name, font=name_font)
    name_text_width = name_bbox[2] - name_bbox[0]
    name_text_height = name_bbox[3] - name_bbox[1]
    name_x = (width - name_text_width) // 2
    name_y = winner_y + winner_text_height + int(height * 0.05)
    draw.text((name_x, name_y), winner_name, font=name_font, fill=WHITE)

    # Trophy/crown emoji (using a simple text emoji for now)
    emoji_font_size = int(height * 0.15)
    emoji_font = get_font(FALLBACK_FONT, emoji_font_size) # Fallback font usually has good emoji support
    emoji_text = "🏆"

    emoji_bbox = draw.textbbox((0, 0), emoji_text, font=emoji_font)
    emoji_width = emoji_bbox[2] - emoji_bbox[0]
    emoji_height = emoji_bbox[3] - emoji_bbox[1]
    emoji_x = (width - emoji_width) // 2
    emoji_y = name_y + name_text_height + int(height * 0.05)
    draw.text((emoji_x, emoji_y), emoji_text, font=emoji_font, fill=accent_color)

    return np.array(img)


if __name__ == "__main__":
    output_dir = "output"
    import os
    os.makedirs(output_dir, exist_ok=True)

    # Test render_vs_split_screen
    print("Generating vs_split_screen.png...")
    vs_frame = render_vs_split_screen(1920, 1080, "Product X", "Product Y")
    Image.fromarray(vs_frame).save(os.path.join(output_dir, "vs_split_screen.png"))

    # Test render_spec_comparison
    print("Generating spec_comparison_a_wins.png...")
    spec_frame_a_wins = render_spec_comparison(1920, 300, "Battery Life", "10 Hours", "8 Hours", winner="a")
    Image.fromarray(spec_frame_a_wins).save(os.path.join(output_dir, "spec_comparison_a_wins.png"))

    print("Generating spec_comparison_b_wins.png...")
    spec_frame_b_wins = render_spec_comparison(1920, 300, "Price", "$199", "$149", winner="b")
    Image.fromarray(spec_frame_b_wins).save(os.path.join(output_dir, "spec_comparison_b_wins.png"))

    print("Generating spec_comparison_no_winner.png...")
    spec_frame_no_winner = render_spec_comparison(1920, 300, "Weight", "200g", "200g", winner="none")
    Image.fromarray(spec_frame_no_winner).save(os.path.join(output_dir, "spec_comparison_no_winner.png"))

    # Test render_scorecard
    print("Generating scorecard.png...")
    sample_scores = [
        {"category": "Sound Quality", "score_a": 8, "score_b": 7},
        {"category": "Comfort", "score_a": 9, "score_b": 8},
        {"category": "Features", "score_a": 7, "score_b": 9},
        {"category": "Battery", "score_a": 8, "score_b": 6},
    ]
    scorecard_frame = render_scorecard(1920, 1080, "Headphones A", "Headphones B", sample_scores)
    Image.fromarray(scorecard_frame).save(os.path.join(output_dir, "scorecard.png"))

    # Test render_price_comparison
    print("Generating price_comparison.png...")
    sample_products = [
        {"name": "Product A", "price": "$49.99", "is_recommended": False},
        {"name": "Product B", "price": "$59.99", "is_recommended": True},
        {"name": "Product C", "price": "$39.99", "is_recommended": False},
    ]
    price_frame = render_price_comparison(1920, 1080, sample_products)
    Image.fromarray(price_frame).save(os.path.join(output_dir, "price_comparison.png"))

    # Test render_winner_reveal
    print("Generating winner_reveal.png...")
    winner_frame = render_winner_reveal(1920, 1080, "Product B")
    Image.fromarray(winner_frame).save(os.path.join(output_dir, "winner_reveal.png"))

    print(f"Sample frames generated in {output_dir}/")
