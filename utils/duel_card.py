import io
import math
import random
from PIL import Image, ImageDraw, ImageFont


def create_circle_mask(size: int) -> Image.Image:
    scale = 4
    dim = size * scale
    mask = Image.new("L", (dim, dim), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([(0, 0), (dim - 1, dim - 1)], fill=255)
    return mask.resize((size, size), Image.Resampling.LANCZOS)


def draw_pip(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float):
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(255, 255, 255, 255))
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=(225, 225, 225, 180), width=1)


def render_3d_die(value: int, size: int = 140) -> Image.Image:
    """
    Renders a single 3D-styled red die at given size with rounded corners,
    depth/bevel, and white pips matching the design.
    """
    scale = 2
    dim = size * scale
    die_img = Image.new("RGBA", (dim + 30, dim + 30), (0, 0, 0, 0))
    draw = ImageDraw.Draw(die_img)

    # 3D shadow / bottom extrusion
    ext_offset_x = 8
    ext_offset_y = 12
    draw.rounded_rectangle(
        [(ext_offset_x, ext_offset_y), (dim + ext_offset_x, dim + ext_offset_y)],
        radius=26,
        fill=(130, 28, 22, 230),
    )
    # Side shadow
    draw.rounded_rectangle(
        [(ext_offset_x // 2, ext_offset_y // 2), (dim + ext_offset_x // 2, dim + ext_offset_y // 2)],
        radius=26,
        fill=(165, 38, 30, 240),
    )

    # Main front face (red rich fill)
    draw.rounded_rectangle(
        [(0, 0), (dim, dim)],
        radius=26,
        fill=(228, 72, 58, 255),
        outline=(255, 125, 110, 240),
        width=3,
    )

    # Top-left highlight bevel
    draw.arc([(4, 4), (dim - 4, dim - 4)], start=180, end=270, fill=(255, 160, 150, 180), width=4)

    # Draw pips
    m = dim // 2
    p1 = dim * 0.28
    p2 = dim * 0.72
    r = dim * 0.088

    positions = []
    if value == 1:
        positions = [(m, m)]
    elif value == 2:
        positions = [(p1, p1), (p2, p2)]
    elif value == 3:
        positions = [(p1, p1), (m, m), (p2, p2)]
    elif value == 4:
        positions = [(p1, p1), (p2, p1), (p1, p2), (p2, p2)]
    elif value == 5:
        positions = [(p1, p1), (p2, p1), (m, m), (p1, p2), (p2, p2)]
    elif value == 6:
        positions = [(p1, p1), (p2, p1), (p1, m), (p2, m), (p1, p2), (p2, p2)]

    for px, py in positions:
        draw_pip(draw, px, py, r)

    return die_img.resize((size + 15, size + 15), Image.Resampling.LANCZOS)


def render_mini_die(value: int, size: int = 26) -> Image.Image:
    """Renders a small square die for the summary bar."""
    scale = 3
    dim = size * scale
    img = Image.new("RGBA", (dim, dim), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle(
        [(0, 0), (dim - 1, dim - 1)],
        radius=int(dim * 0.22),
        fill=(225, 68, 54, 255),
        outline=(255, 115, 100, 255),
        width=2,
    )

    m = dim / 2.0
    p1 = dim * 0.28
    p2 = dim * 0.72
    r = dim * 0.085

    positions = []
    if value == 1:
        positions = [(m, m)]
    elif value == 2:
        positions = [(p1, p1), (p2, p2)]
    elif value == 3:
        positions = [(p1, p1), (m, m), (p2, p2)]
    elif value == 4:
        positions = [(p1, p1), (p2, p1), (p1, p2), (p2, p2)]
    elif value == 5:
        positions = [(p1, p1), (p2, p1), (m, m), (p1, p2), (p2, p2)]
    elif value == 6:
        positions = [(p1, p1), (p2, p1), (p1, m), (p2, m), (p1, p2), (p2, p2)]

    for px, py in positions:
        draw.ellipse([(px - r, py - r), (px + r, py + r)], fill=(255, 255, 255, 255))

    return img.resize((size, size), Image.Resampling.LANCZOS)


def render_duel_card(
    creator_avatar: bytes | None,
    opponent_avatar: bytes | None,
    creator_name: str,
    opponent_name: str,
    creator_dice: tuple[int, int],
    opponent_dice: tuple[int, int],
    bet: int = 100,
) -> io.BytesIO:
    W, H = 960, 420
    canvas = Image.new("RGBA", (W, H), (14, 16, 20, 255))
    draw = ImageDraw.Draw(canvas)

    # Fonts
    try:
        font_name = ImageFont.truetype("fonts/bold.ttf", 20)
        font_sum = ImageFont.truetype("fonts/bold.ttf", 22)
        font_sign = ImageFont.truetype("fonts/bold.ttf", 48)
        font_title = ImageFont.truetype("fonts/bold.ttf", 15)
    except Exception:
        font_name = ImageFont.load_default()
        font_sum = font_name
        font_sign = font_name
        font_title = font_name

    # Outer border / rounded container
    draw.rounded_rectangle(
        [(10, 10), (W - 10, H - 10)],
        radius=24,
        fill=(18, 20, 25, 255),
        outline=(38, 42, 52, 255),
        width=3,
    )

    # 1. Arena Circles (Left & Right)
    left_cx, left_cy = 265, 165
    right_cx, right_cy = 695, 165
    arena_r = 135

    # Left Arena Plate
    draw.ellipse(
        [(left_cx - arena_r, left_cy - arena_r), (left_cx + arena_r, left_cy + arena_r)],
        fill=(42, 45, 53, 255),
        outline=(58, 63, 74, 255),
        width=2,
    )
    draw.ellipse(
        [(left_cx - arena_r + 14, left_cy - arena_r + 14), (left_cx + arena_r - 14, left_cy + arena_r - 14)],
        outline=(50, 54, 64, 180),
        width=1,
    )

    # Right Arena Plate
    draw.ellipse(
        [(right_cx - arena_r, right_cy - arena_r), (right_cx + arena_r, right_cy + arena_r)],
        fill=(42, 45, 53, 255),
        outline=(58, 63, 74, 255),
        width=2,
    )
    draw.ellipse(
        [(right_cx - arena_r + 14, right_cy - arena_r + 14), (right_cx + arena_r - 14, right_cy + arena_r - 14)],
        outline=(50, 54, 64, 180),
        width=1,
    )

    # 2. Place 3D Dice with natural angles
    die_size = 78
    # Left dice
    d1_img = render_3d_die(creator_dice[0], die_size)
    d1_rot = d1_img.rotate(random.choice([-24, -18, -28]), resample=Image.Resampling.BICUBIC, expand=True)
    canvas.paste(d1_rot, (left_cx - 95, left_cy - 48), d1_rot)

    d2_img = render_3d_die(creator_dice[1], die_size)
    d2_rot = d2_img.rotate(random.choice([20, 28, 35]), resample=Image.Resampling.BICUBIC, expand=True)
    canvas.paste(d2_rot, (left_cx + 10, left_cy - 75), d2_rot)

    # Right dice
    d3_img = render_3d_die(opponent_dice[0], die_size)
    d3_rot = d3_img.rotate(random.choice([-15, -22, -10]), resample=Image.Resampling.BICUBIC, expand=True)
    canvas.paste(d3_rot, (right_cx - 90, right_cy - 78), d3_rot)

    d4_img = render_3d_die(opponent_dice[1], die_size)
    d4_rot = d4_img.rotate(random.choice([25, 32, 40]), resample=Image.Resampling.BICUBIC, expand=True)
    canvas.paste(d4_rot, (right_cx + 15, right_cy - 35), d4_rot)

    # 3. Middle Diamond comparison badge
    mid_cx, mid_cy = 480, 165
    dia_r = 46
    dia_pts = [
        (mid_cx, mid_cy - dia_r),
        (mid_cx + dia_r, mid_cy),
        (mid_cx, mid_cy + dia_r),
        (mid_cx - dia_r, mid_cy),
    ]
    draw.polygon(dia_pts, fill=(22, 24, 28, 255), outline=(225, 68, 54, 255), width=3)
    inner_r = dia_r - 8
    inner_pts = [
        (mid_cx, mid_cy - inner_r),
        (mid_cx + inner_r, mid_cy),
        (mid_cx, mid_cy + inner_r),
        (mid_cx - inner_r, mid_cy),
    ]
    draw.polygon(inner_pts, outline=(70, 25, 30, 255), width=1)

    c_sum = sum(creator_dice)
    o_sum = sum(opponent_dice)
    if c_sum > o_sum:
        sign = ">"
    elif c_sum < o_sum:
        sign = "<"
    else:
        sign = "="

    sb = draw.textbbox((0, 0), sign, font=font_sign)
    tx = int(mid_cx - (sb[0] + sb[2]) / 2)
    ty = int(mid_cy - (sb[1] + sb[3]) / 2)
    draw.text((tx, ty), sign, font=font_sign, fill=(245, 95, 75, 255))

    # 4. Bottom Player Summary Bar
    bar_x, bar_y = 36, 325
    bar_w, bar_h = W - 72, 72
    draw.rounded_rectangle(
        [(bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h)],
        radius=18,
        fill=(22, 25, 30, 255),
        outline=(38, 42, 52, 255),
        width=2,
    )

    av_size = 46
    mask_av = create_circle_mask(av_size)

    def draw_player_av(av_bytes, px, py, initial_char):
        if av_bytes:
            try:
                raw = Image.open(io.BytesIO(av_bytes)).convert("RGBA")
                scaled = raw.resize((av_size, av_size), Image.Resampling.LANCZOS)
                canvas.paste(scaled, (px, py), mask_av)
                draw.ellipse([(px - 1, py - 1), (px + av_size + 1, py + av_size + 1)], outline=(70, 75, 90, 255), width=2)
                return
            except Exception:
                pass
        draw.ellipse([(px, py), (px + av_size, py + av_size)], fill=(45, 50, 62, 255), outline=(70, 75, 90, 255), width=2)
        cb = draw.textbbox((0, 0), initial_char.upper(), font=font_title)
        cw = cb[2] - cb[0]
        ch = cb[3] - cb[1]
        draw.text((px + (av_size - cw) // 2, py + (av_size - ch) // 2 - 2), initial_char.upper(), font=font_title, fill=(240, 240, 240, 255))

    # --- LEFT PLAYER (Creator) ---
    c_av_x = bar_x + 14
    c_av_y = bar_y + (bar_h - av_size) // 2
    draw_player_av(creator_avatar, c_av_x, c_av_y, creator_name[:1] if creator_name else "A")

    c_name = (creator_name[:14] + "…") if creator_name and len(creator_name) > 15 else (creator_name or "Игрок 1")
    draw.text((c_av_x + av_size + 14, bar_y + 24), c_name, font=font_name, fill=(245, 245, 250, 255))

    c_box_x = mid_cx - 75
    c_box_y = bar_y + 16
    draw.rounded_rectangle([(c_box_x, c_box_y), (c_box_x + 40, c_box_y + 40)], radius=8, fill=(35, 38, 48, 255), outline=(50, 55, 68, 255), width=1)
    c_sum_str = str(c_sum)
    sb1 = draw.textbbox((0, 0), c_sum_str, font=font_sum)
    sw1 = sb1[2] - sb1[0]
    draw.text((c_box_x + (40 - sw1) // 2, c_box_y + 7), c_sum_str, font=font_sum, fill=(255, 255, 255, 255))

    mini_d2 = render_mini_die(creator_dice[1], 28)
    mini_d1 = render_mini_die(creator_dice[0], 28)
    canvas.paste(mini_d2, (c_box_x - 34, c_box_y + 6), mini_d2)
    canvas.paste(mini_d1, (c_box_x - 70, c_box_y + 6), mini_d1)

    # --- RIGHT PLAYER (Opponent) ---
    o_box_x = mid_cx + 35
    o_box_y = bar_y + 16
    draw.rounded_rectangle([(o_box_x, o_box_y), (o_box_x + 40, o_box_y + 40)], radius=8, fill=(35, 38, 48, 255), outline=(50, 55, 68, 255), width=1)
    o_sum_str = str(o_sum)
    sb2 = draw.textbbox((0, 0), o_sum_str, font=font_sum)
    sw2 = sb2[2] - sb2[0]
    draw.text((o_box_x + (40 - sw2) // 2, o_box_y + 7), o_sum_str, font=font_sum, fill=(255, 255, 255, 255))

    mini_d3 = render_mini_die(opponent_dice[0], 28)
    mini_d4 = render_mini_die(opponent_dice[1], 28)
    canvas.paste(mini_d3, (o_box_x + 46, o_box_y + 6), mini_d3)
    canvas.paste(mini_d4, (o_box_x + 82, o_box_y + 6), mini_d4)

    o_av_x = bar_x + bar_w - av_size - 14
    o_av_y = bar_y + (bar_h - av_size) // 2
    draw_player_av(opponent_avatar, o_av_x, o_av_y, opponent_name[:1] if opponent_name else "B")

    o_name = (opponent_name[:14] + "…") if opponent_name and len(opponent_name) > 15 else (opponent_name or "Игрок 2")
    nb = draw.textbbox((0, 0), o_name, font=font_name)
    nw = nb[2] - nb[0]
    draw.text((o_av_x - nw - 14, bar_y + 24), o_name, font=font_name, fill=(245, 245, 250, 255))

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
