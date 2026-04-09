
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import random

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Brand colors
DARK_PINK = (196, 80, 122)
NEAR_BLACK = (10, 10, 15)
DARK_GRAY = (25, 25, 35)

def generate_background(width, height, style="gradient", accent_color=DARK_PINK, seed=None):
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    if style == "gradient":
        return _generate_gradient(width, height, accent_color)
    elif style == "mesh_gradient":
        return _generate_mesh_gradient(width, height, accent_color)
    elif style == "geometric":
        return _generate_geometric(width, height, accent_color)
    elif style == "circuit":
        return _generate_circuit(width, height, accent_color)
    elif style == "wave":
        return _generate_wave(width, height, accent_color)
    elif style == "bokeh":
        return _generate_bokeh(width, height, accent_color)
    elif style == "noise":
        return _generate_noise(width, height, accent_color)
    elif style == "radial":
        return _generate_radial(width, height, accent_color)
    elif style == "grid":
        return _generate_grid(width, height, accent_color)
    elif style == "abstract":
        return _generate_abstract(width, height, accent_color)
    else:
        raise ValueError(f"Unknown style: {style}")

def _generate_gradient(width, height, accent_color):
    image = Image.new("RGB", (width, height), NEAR_BLACK)
    draw = ImageDraw.Draw(image)

    for y in range(height):
        r = int(NEAR_BLACK[0] + (accent_color[0] - NEAR_BLACK[0]) * (y / height))
        g = int(NEAR_BLACK[1] + (accent_color[1] - NEAR_BLACK[1]) * (y / height))
        b = int(NEAR_BLACK[2] + (accent_color[2] - NEAR_BLACK[2]) * (y / height))
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return image

def _generate_mesh_gradient(width, height, accent_color):
    image = Image.new("RGB", (width, height), NEAR_BLACK)
    pixels = np.zeros((height, width, 3), dtype=np.float32)

    points = [
        (random.randint(0, width), random.randint(0, height), np.array([random.randint(0, 50), random.randint(0, 50), random.randint(0, 50)], dtype=np.float32)),
        (random.randint(0, width), random.randint(0, height), np.array(accent_color, dtype=np.float32)),
        (random.randint(0, width), random.randint(0, height), np.array(DARK_GRAY, dtype=np.float32)),
        (random.randint(0, width), random.randint(0, height), np.array(NEAR_BLACK, dtype=np.float32)),
    ]

    Y, X = np.mgrid[0:height, 0:width]

    for px, py, color in points:
        distance = np.sqrt((X - px)**2 + (Y - py)**2)
        weight = 1 / (distance + 1e-6)
        
        # Reshape color to (1, 1, 3) for broadcasting
        pixels += color * weight[:, :, np.newaxis]

    # Normalize weights
    total_weights = np.zeros((height, width), dtype=np.float32)
    for px, py, _ in points:
        distance = np.sqrt((X - px)**2 + (Y - py)**2)
        total_weights += 1 / (distance + 1e-6)
    
    # Avoid division by zero
    total_weights[total_weights == 0] = 1e-6

    pixels /= total_weights[:, :, np.newaxis]
    pixels = np.clip(pixels, 0, 255)

    return Image.fromarray(pixels.astype(np.uint8))

def _generate_geometric(width, height, accent_color):
    image = Image.new("RGB", (width, height), NEAR_BLACK)
    draw = ImageDraw.Draw(image, "RGBA")

    num_shapes = random.randint(10, 30)
    for _ in range(num_shapes):
        shape_type = random.choice(["triangle", "hexagon", "circle"])
        opacity = random.randint(10, 50) # Low opacity
        fill_color = accent_color + (opacity,)

        if shape_type == "triangle":
            p1 = (random.randint(0, width), random.randint(0, height))
            p2 = (random.randint(0, width), random.randint(0, height))
            p3 = (random.randint(0, width), random.randint(0, height))
            draw.polygon([p1, p2, p3], fill=fill_color)
        elif shape_type == "hexagon":
            center_x, center_y = random.randint(0, width), random.randint(0, height)
            radius = random.randint(20, 100)
            points = []
            for i in range(6):
                angle_deg = 60 * i - 30 # Start from top flat side
                angle_rad = np.pi / 180 * angle_deg
                x = center_x + radius * np.cos(angle_rad)
                y = center_y + radius * np.sin(angle_rad)
                points.append((x, y))
            draw.polygon(points, fill=fill_color)
        elif shape_type == "circle":
            center_x, center_y = random.randint(0, width), random.randint(0, height)
            radius = random.randint(20, 100)
            draw.ellipse((center_x - radius, center_y - radius, center_x + radius, center_y + radius), fill=fill_color)
    return image

def _generate_circuit(width, height, accent_color):
    image = Image.new("RGB", (width, height), NEAR_BLACK)
    draw = ImageDraw.Draw(image)

    line_color = accent_color # Use accent color for glowing lines
    num_lines = random.randint(50, 150)
    for _ in range(num_lines):
        start_x, start_y = random.randint(0, width), random.randint(0, height)
        end_x, end_y = random.randint(0, width), random.randint(0, height)
        line_width = random.randint(1, 3)
        draw.line([(start_x, start_y), (end_x, end_y)], fill=line_color, width=line_width)
    
    # Add some 
    # Add some subtle glow effect (blur)
    image = image.filter(ImageFilter.GaussianBlur(radius=2))
    return image

def _generate_wave(width, height, accent_color):
    image = Image.new("RGB", (width, height), NEAR_BLACK)
    pixels = np.array(image)

    frequency_x = random.uniform(0.005, 0.02)
    frequency_y = random.uniform(0.005, 0.02)
    amplitude = random.uniform(10, 30)
    phase_shift_x = random.uniform(0, 2 * np.pi)
    phase_shift_y = random.uniform(0, 2 * np.pi)

    Y, X = np.mgrid[0:height, 0:width]

    wave1 = amplitude * np.sin(X * frequency_x + phase_shift_x)
    wave2 = amplitude * np.sin(Y * frequency_y + phase_shift_y)
    
    intensity = (wave1 + wave2) / (2 * amplitude)
    intensity = (intensity + 1) / 2

    r = NEAR_BLACK[0] * (1 - intensity) + accent_color[0] * intensity
    g = NEAR_BLACK[1] * (1 - intensity) + accent_color[1] * intensity
    b = NEAR_BLACK[2] * (1 - intensity) + accent_color[2] * intensity
    pixels = np.stack([r, g, b], axis=-1)

    return Image.fromarray(pixels.astype(np.uint8))

def _generate_bokeh(width, height, accent_color):
    image = Image.new("RGB", (width, height), NEAR_BLACK)
    draw = ImageDraw.Draw(image, "RGBA")

    num_circles = random.randint(50, 150)
    for _ in range(num_circles):
        center_x = random.randint(0, width)
        center_y = random.randint(0, height)
        radius = random.randint(10, 100)
        opacity = random.randint(10, 80)
        
        # Randomly choose between accent color and dark gray for bokeh circles
        color_choice = random.choice([accent_color, DARK_GRAY])
        fill_color = color_choice + (opacity,)

        draw.ellipse((center_x - radius, center_y - radius, center_x + radius, center_y + radius), fill=fill_color)
    
    image = image.filter(ImageFilter.GaussianBlur(radius=5))
    return image

def _generate_noise(width, height, accent_color):
    image = Image.new("RGB", (width, height), NEAR_BLACK)
    pixels = np.array(image)

    # Generate Perlin-like noise
    scale = 100.0
    octaves = 6
    persistence = 0.5
    lacunarity = 2.0

    # Generate random noise and smooth it
    noise_map = np.random.rand(height, width)
    # Apply a simple blur to simulate Perlin-like noise
    # This is a simplification and not true Perlin noise, but faster
    noise_image = Image.fromarray((noise_map * 255).astype(np.uint8))
    noise_image = noise_image.filter(ImageFilter.GaussianBlur(radius=10))
    noise_map = np.array(noise_image) / 255.0
    
    # Normalize noise to 0-1
    noise_map = (noise_map - noise_map.min()) / (noise_map.max() - noise_map.min())

    # Apply noise and blend with accent color
    intensity = noise_map
    r = NEAR_BLACK[0] * (1 - intensity) + accent_color[0] * intensity * 0.5
    g = NEAR_BLACK[1] * (1 - intensity) + accent_color[1] * intensity * 0.5
    b = NEAR_BLACK[2] * (1 - intensity) + accent_color[2] * intensity * 0.5
    pixels = np.stack([r, g, b], axis=-1)

    return Image.fromarray(pixels.astype(np.uint8))

def _generate_radial(width, height, accent_color):
    image = Image.new("RGB", (width, height), NEAR_BLACK)
    pixels = np.array(image)

    center_x, center_y = width // 2, height // 2
    max_distance = np.sqrt(center_x**2 + center_y**2)

    for y in range(height):
        for x in range(width):
            distance = np.sqrt((x - center_x)**2 + (y - center_y)**2)
            intensity = 1 - (distance / max_distance) # Closer to center is brighter
            intensity = max(0, min(1, intensity)) # Clamp between 0 and 1

            r = int(NEAR_BLACK[0] * (1 - intensity) + accent_color[0] * intensity)
            g = int(NEAR_BLACK[1] * (1 - intensity) + accent_color[1] * intensity)
            b = int(NEAR_BLACK[2] * (1 - intensity) + accent_color[2] * intensity)
            pixels[y, x] = [r, g, b]

    return Image.fromarray(pixels.astype(np.uint8))

def _generate_grid(width, height, accent_color):
    image = Image.new("RGB", (width, height), NEAR_BLACK)
    draw = ImageDraw.Draw(image)

    grid_size = random.randint(30, 80)
    dot_radius = random.randint(1, 2)
    grid_color = DARK_GRAY # Subtle grid color

    for x in range(0, width, grid_size):
        for y in range(0, height, grid_size):
            draw.ellipse((x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius), fill=grid_color)
    return image

def _generate_abstract(width, height, accent_color):
    image = Image.new("RGB", (width, height), NEAR_BLACK)
    draw = ImageDraw.Draw(image, "RGBA")

    num_blobs = random.randint(5, 15)
    for _ in range(num_blobs):
        center_x = random.randint(0, width)
        center_y = random.randint(0, height)
        radius = random.randint(50, 200)
        opacity = random.randint(20, 60)
        
        # Randomly choose between accent color and dark gray for blobs
        color_choice = random.choice([accent_color, DARK_GRAY])
        fill_color = color_choice + (opacity,)

        # Draw a somewhat irregular ellipse to simulate an organic blob
        offset_x = random.randint(-radius // 4, radius // 4)
        offset_y = random.randint(-radius // 4, radius // 4)
        draw.ellipse((center_x - radius + offset_x, center_y - radius + offset_y, 
                      center_x + radius + offset_x, center_y + radius + offset_y), fill=fill_color)
    
    image = image.filter(ImageFilter.GaussianBlur(radius=10))
    return image

def generate_background_sequence(width, height, num_frames, style="gradient", accent_color=DARK_PINK):
    frames = []
    for i in range(num_frames):
        # Vary the seed or parameters slightly for each frame
        seed = random.randint(0, 100000) + i # Simple variation
        frame = generate_background(width, height, style, accent_color, seed=seed)
        frames.append(frame)
    return frames

def get_style_for_content(content_style, hook_type):
    style_map = {
        "vs_battle": "geometric",
        "honest_review": "bokeh",
        "budget_challenge": "mesh_gradient",
        "tutorial": "grid",
        "news": "circuit",
        "storytime": "wave",
        "meditation": "radial",
        "action": "noise",
        "abstract_art": "abstract",
        "default": "gradient",
    }
    # Prioritize content_style if it exists, otherwise check hook_type
    return style_map.get(content_style, style_map.get(hook_type, "gradient"))

def apply_vignette(image, strength=0.5):
    width, height = image.size
    # Create a black image for the vignette
    vignette = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(vignette)

    # Draw an ellipse in the center, filled with white, then blur it
    # The size of the ellipse determines the vignette's softness and spread
    ellipse_width = int(width * 0.8)
    ellipse_height = int(height * 0.8)
    draw.ellipse(((width - ellipse_width) // 2, (height - ellipse_height) // 2,
                  (width + ellipse_width) // 2, (height + ellipse_height) // 2), fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=width / 3))

    # Apply the vignette to the image
    # Convert image to RGBA to handle alpha channel for blending
    img_rgba = image.convert("RGBA")
    vignette_mask = Image.new('RGBA', (width, height))
    # Create a black overlay with varying alpha based on the vignette mask
    vignette_pixels = np.array(vignette)
    alpha_channel = (255 - vignette_pixels * strength).astype(np.uint8)
    vignette_mask_pixels = np.zeros((height, width, 4), dtype=np.uint8)
    vignette_mask_pixels[:, :, 3] = alpha_channel
    vignette_mask = Image.fromarray(vignette_mask_pixels)

    # Composite the original image with the vignette mask
    return Image.alpha_composite(img_rgba, vignette_mask).convert("RGB")

def apply_film_grain(image, intensity=0.03):
    width, height = image.size
    pixels = np.array(image).astype(np.float32)

    grain = np.random.normal(0, intensity * 255, (height, width, 3))
    pixels += grain
    pixels = np.clip(pixels, 0, 255)

    return Image.fromarray(pixels.astype(np.uint8))


if __name__ == "__main__":
    print("Generating sample backgrounds...")
    output_dir = "/home/ubuntu/shadowcast/samples"
    os.makedirs(output_dir, exist_ok=True)

    WIDTH, HEIGHT = 1920, 1080

    styles = [
        "gradient", "mesh_gradient", "geometric", "circuit", "wave",
        "bokeh", "noise", "radial", "grid", "abstract"
    ]

    for style_name in styles:
        print(f"Generating {style_name} style...")
        img = generate_background(WIDTH, HEIGHT, style=style_name, seed=42)
        img.save(os.path.join(output_dir, f"background_{style_name}.png"))
    
    # Test background sequence
    print("Generating background sequence...")
    frames = generate_background_sequence(WIDTH, HEIGHT, num_frames=5, style="wave", accent_color=DARK_PINK)
    for i, frame in enumerate(frames):
        frame.save(os.path.join(output_dir, f"sequence_wave_frame_{i:02d}.png"))

    # Test vignette and film grain
    print("Generating image with vignette and film grain...")
    base_img = generate_background(WIDTH, HEIGHT, style="gradient", seed=42)
    vignetted_img = apply_vignette(base_img)
    vignetted_img.save(os.path.join(output_dir, "background_gradient_vignette.png"))

    grained_img = apply_film_grain(base_img)
    grained_img.save(os.path.join(output_dir, "background_gradient_filmgrain.png"))

    vignetted_grained_img = apply_film_grain(apply_vignette(base_img))
    vignetted_grained_img.save(os.path.join(output_dir, "background_gradient_vignette_filmgrain.png"))

    print(f"Sample backgrounds saved to {output_dir}")

    # Test get_style_for_content
    print("Testing get_style_for_content...")
    print(f"vs_battle -> {get_style_for_content('vs_battle', '')}")
    print(f"honest_review -> {get_style_for_content('honest_review', '')}")
    print(f"budget_challenge -> {get_style_for_content('budget_challenge', '')}")
    print(f"unknown_content -> {get_style_for_content('unknown_content', 'tutorial')}")
    print(f"unknown_content_unknown_hook -> {get_style_for_content('unknown_content_unknown_hook', '')}")
