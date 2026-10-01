import io
import math
from PIL import Image, ImageDraw, ImageFont

from utils.leaderboard_card import get_emoji_icon


def draw_notched_ticket(
    draw: ImageDraw.ImageDraw,
    canvas: Image.Image,
    x: int,
    y: int,
    w: int,
    h: int,
    number_str: str,
    font: ImageFont.ImageFont,
    state: str,  # "free", "sold", "winning"
    bg_color: tuple[int, int, int] = (18, 20, 25),
):
    """
    Draws a single lottery ticket badge with notches on left and right sides.
    """
    r_notch = 4
    cy = y + h // 2

    if state == "winning":
        fill_col = (238, 52, 65, 255)
        outline_col = (255, 130, 140, 255)
        text_col = (255, 255, 255, 255)
        # Glow around winning ticket
        draw.rounded_rectangle(
            [(x - 2, y - 2), (x + w + 1, y + h + 1)],
            radius=6,
            fill=(238, 52, 65, 80),
        )
    elif state == "sold":
        fill_col = (68, 22, 28, 255)
        outline_col = (98, 30, 38, 255)
        text_col = (210, 115, 125, 255)
    else:  # free
        fill_col = (31, 34, 41, 255)
        outline_col = (45, 50, 60, 255)
        text_col = (135, 142, 155, 255)

    # Base rounded rectangle
    draw.rounded_rectangle([(x, y), (x + w - 1, y + h - 1)], radius=5, fill=fill_col, outline=outline_col, width=1)

    # Cutout notches on left and right
    draw.ellipse([(x - r_notch, cy - r_notch), (x + r_notch, cy + r_notch)], fill=bg_color, outline=outline_col, width=1)
    draw.ellipse([(x + w - 1 - r_notch, cy - r_notch), (x + w - 1 + r_notch, cy + r_notch)], fill=bg_color, outline=outline_col, width=1)

    # Text centered
    tb = draw.textbbox((0, 0), number_str, font=font)
    tw = tb[2] - tb[0]
    th = tb[3] - tb[1]
    tx = x + (w - tw) // 2
    ty = y + (h - th) // 2 - 1
    draw.text((tx, ty), number_str, font=font, fill=text_col)


def render_lottery_card(
    prize: int,
    ticket_price: int,
    sold_count: int,
    sold_tickets: set[int] | list[int] | None = None,
    winning_ticket: int | None = None,
    total_tickets: int = 100,
) -> io.BytesIO:
    """
    Renders the 10x10 lottery ticket card matching the user's reference design.
    """
    W, H = 1060, 520
    BG_MAIN = (18, 20, 25)
    canvas = Image.new("RGBA", (W, H), (14, 16, 20, 255))
    draw = ImageDraw.Draw(canvas)

    # Fonts
    try:
        font_title = ImageFont.truetype("fonts/bold.ttf", 26)
        font_metric_val = ImageFont.truetype("fonts/bold.ttf", 20)
        font_metric_lbl = ImageFont.truetype("fonts/default.ttf", 12)
        font_sub = ImageFont.truetype("fonts/default.ttf", 13)
        font_ticket = ImageFont.truetype("fonts/bold.ttf", 12)
        font_ticket_win = ImageFont.truetype("fonts/bold.ttf", 13)
        font_legend = ImageFont.truetype("fonts/default.ttf", 12)
    except Exception:
        font_title = ImageFont.load_default()
        font_metric_val = font_title
        font_metric_lbl = font_title
        font_sub = font_title
        font_ticket = font_title
        font_ticket_win = font_title
        font_legend = font_title

    # Outer container with rounded corners and sleek border
    draw.rounded_rectangle(
        [(10, 10), (W - 10, H - 10)],
        radius=22,
        fill=BG_MAIN,
        outline=(36, 40, 50, 255),
        width=2,
    )

    # 1. Header Section
    header_x, header_y = 35, 26
    # Title & Subtitle
    draw.text((header_x, header_y), "Лотерея", font=font_title, fill=(245, 248, 252, 255))
    draw.text((header_x, header_y + 34), "100 билетов, один победный", font=font_sub, fill=(125, 134, 148, 255))

    # Metrics (Prize, Ticket Price, Sold)
    coin_icon = get_emoji_icon("coin", 20)

    # Prize
    m1_x = 420
    draw.text((m1_x, header_y + 4), "Приз", font=font_metric_lbl, fill=(130, 138, 150, 255))
    prize_str = f"{prize:,}".replace(",", " ")
    draw.text((m1_x, header_y + 24), prize_str, font=font_metric_val, fill=(245, 248, 252, 255))
    pb = draw.textbbox((0, 0), prize_str, font=font_metric_val)
    pw = pb[2] - pb[0]
    if coin_icon:
        canvas.paste(coin_icon, (m1_x + pw + 6, header_y + 24 + 1), mask=coin_icon)

    # Price
    m2_x = 590
    draw.text((m2_x, header_y + 4), "Цена билета", font=font_metric_lbl, fill=(130, 138, 150, 255))
    price_str = f"{ticket_price:,}".replace(",", " ")
    draw.text((m2_x, header_y + 24), price_str, font=font_metric_val, fill=(245, 248, 252, 255))
    tpb = draw.textbbox((0, 0), price_str, font=font_metric_val)
    tpw = tpb[2] - tpb[0]
    if coin_icon:
        canvas.paste(coin_icon, (m2_x + tpw + 6, header_y + 24 + 1), mask=coin_icon)

    # Sold
    m3_x = 760
    draw.text((m3_x, header_y + 4), "Продано", font=font_metric_lbl, fill=(130, 138, 150, 255))
    draw.text((m3_x, header_y + 24), f"{sold_count} из {total_tickets}", font=font_metric_val, fill=(245, 248, 252, 255))

    # Decorative ticket watermark on top right
    watermark_col = (255, 255, 255, 18)
    wm_x, wm_y = W - 145, 24
    for offset in [(0, 10), (35, 0), (70, -10)]:
        ox, oy = wm_x + offset[0], wm_y + offset[1]
        draw.rounded_rectangle([(ox, oy), (ox + 55, oy + 38)], radius=6, outline=watermark_col, width=1)
        draw.ellipse([(ox - 4, oy + 15), (ox + 4, oy + 23)], outline=watermark_col, width=1)
        draw.ellipse([(ox + 51, oy + 15), (ox + 59, oy + 23)], outline=watermark_col, width=1)

    # Subtle divider line
    draw.line([(header_x, header_y + 68), (W - 35, header_y + 68)], fill=(32, 36, 45, 255), width=1)

    # 2. Legend / Sub-bar
    sub_y = header_y + 78
    draw.text((header_x, sub_y), "Билеты", font=font_sub, fill=(170, 178, 192, 255))

    # Legend items on right
    # Winning
    leg_win_x = W - 120
    draw_notched_ticket(draw, canvas, leg_win_x, sub_y - 2, 24, 18, "", font_ticket, "winning", bg_color=BG_MAIN)
    draw.text((leg_win_x + 30, sub_y), "Победный", font=font_legend, fill=(210, 215, 225, 255))

    # Sold
    leg_sold_x = leg_win_x - 120
    draw_notched_ticket(draw, canvas, leg_sold_x, sub_y - 2, 24, 18, "", font_ticket, "sold", bg_color=BG_MAIN)
    draw.text((leg_sold_x + 30, sub_y), "Продан", font=font_legend, fill=(210, 215, 225, 255))

    # Free
    leg_free_x = leg_sold_x - 130
    draw_notched_ticket(draw, canvas, leg_free_x, sub_y - 2, 24, 18, "", font_ticket, "free", bg_color=BG_MAIN)
    draw.text((leg_free_x + 30, sub_y), "Свободен", font=font_legend, fill=(210, 215, 225, 255))

    # 3. 10x10 Ticket Grid
    grid_start_x = 35
    grid_start_y = sub_y + 26
    t_width = 92
    t_height = 32
    gap_x = 8
    gap_y = 6

    sold_set = set(sold_tickets) if sold_tickets else set()

    for i in range(total_tickets):
        num = i + 1
        row = i // 10
        col = i % 10

        tx = grid_start_x + col * (t_width + gap_x)
        ty = grid_start_y + row * (t_height + gap_y)

        if winning_ticket is not None and num == winning_ticket:
            state = "winning"
            font_to_use = font_ticket_win
        elif num in sold_set:
            state = "sold"
            font_to_use = font_ticket
        else:
            state = "free"
            font_to_use = font_ticket

        draw_notched_ticket(
            draw,
            canvas,
            tx,
            ty,
            t_width,
            t_height,
            f"{num:03d}",
            font_to_use,
            state,
            bg_color=BG_MAIN,
        )

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
