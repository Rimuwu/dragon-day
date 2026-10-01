import io
import math
from PIL import Image, ImageDraw, ImageFont

from utils.leaderboard_card import get_emoji_icon


def create_circle_mask(size: int) -> Image.Image:
    scale = 4
    dim = size * scale
    mask = Image.new("L", (dim, dim), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([(0, 0), (dim - 1, dim - 1)], fill=255)
    return mask.resize((size, size), Image.Resampling.LANCZOS)


def _draw_initials_avatar(size: int, name: str, bg_color: tuple, text_color: tuple, font: ImageFont.ImageFont) -> Image.Image:
    img = Image.new("RGBA", (size, size), bg_color)
    draw = ImageDraw.Draw(img)
    initials = "".join([part[0].upper() for part in name.split()[:2] if part]) or "?"
    tb = draw.textbbox((0, 0), initials, font=font)
    tw = tb[2] - tb[0]
    th = tb[3] - tb[1]
    draw.text(((size - tw) // 2, (size - th) // 2 - tb[1]), initials, font=font, fill=text_color)
    mask = create_circle_mask(size)
    output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    output.paste(img, (0, 0), mask=mask)
    return output


def render_bet_card(
    candidates: list[dict],
    bet_type: str = "day",
    bet_date: str = "",
    min_bet: int = 10,
    total_participants: int = 0,
) -> io.BytesIO:
    """
    Renders an ultra-sleek, modern Pillow card showing today's betting candidate pool.
    - Day Dragon: Golden/Sun theme
    - Evil Dragon: Crimson/Flame theme
    """
    N = len(candidates)
    two_rows = N > 4
    W = 960
    H = 640 if two_rows else 450

    canvas = Image.new("RGBA", (W, H), (14, 16, 20, 255))
    draw = ImageDraw.Draw(canvas)

    # Fonts
    try:
        font_title = ImageFont.truetype("fonts/bold.ttf", 22)
        font_sub = ImageFont.truetype("fonts/default.ttf", 13)
        font_name = ImageFont.truetype("fonts/bold.ttf", 15)
        font_badge = ImageFont.truetype("fonts/bold.ttf", 13)
        font_coef = ImageFont.truetype("fonts/bold.ttf", 13)
        font_bets = ImageFont.truetype("fonts/default.ttf", 12)
        font_footer = ImageFont.truetype("fonts/default.ttf", 12)
        font_initials = ImageFont.truetype("fonts/bold.ttf", 26 if not two_rows else 22)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = font_title
        font_name = font_title
        font_badge = font_title
        font_coef = font_title
        font_bets = font_title
        font_footer = font_title
        font_initials = font_title

    # Palette
    is_day = bet_type == "day"
    if is_day:
        accent_color = (255, 185, 45, 255)
        accent_pill_bg = (48, 38, 16, 255)
        accent_pill_border = (195, 140, 30, 255)
        ring_color = (255, 195, 55, 255)
        title_text = "ПУЛ ПРЕТЕНДЕНТОВ • ДРАКОН ДНЯ"
        sub_text = "Выберите фаворита среди кандидатов  |  Итоги подводятся ежедневно"
    else:
        accent_color = (255, 75, 95, 255)
        accent_pill_bg = (48, 16, 22, 255)
        accent_pill_border = (195, 45, 65, 255)
        ring_color = (255, 80, 100, 255)
        title_text = "ПУЛ ПРЕТЕНДЕНТОВ • ЗЛОЙ ДРАКОН"
        sub_text = "Кто посеет хаос в чате?  |  Итоги подводятся ежедневно"

    # Outer container with rounded corners and border
    draw.rounded_rectangle(
        [(10, 10), (W - 10, H - 10)],
        radius=24,
        fill=(18, 20, 26, 255),
        outline=(38, 42, 54, 255),
        width=2,
    )

    # Accent top indicator bar
    bar_w = 120
    draw.rounded_rectangle(
        [((W - bar_w) // 2, 10), ((W + bar_w) // 2, 13)],
        radius=2,
        fill=accent_color,
    )

    # Header title
    tb = draw.textbbox((0, 0), title_text, font=font_title)
    tw = tb[2] - tb[0]
    draw.text(((W - tw) // 2, 24), title_text, font=font_title, fill=(245, 248, 252, 255))

    # Subtitle
    sb = draw.textbbox((0, 0), sub_text, font=font_sub)
    sw = sb[2] - sb[0]
    draw.text(((W - sw) // 2, 54), sub_text, font=font_sub, fill=(140, 148, 165, 255))

    # Grid arrangement
    padding_x = 30
    gap_x = 16
    gap_y = 16

    if not two_rows:
        # Single row layout
        cols = N
        card_w = (W - padding_x * 2 - (cols - 1) * gap_x) // cols
        card_h = 280
        top_y = 90
        positions = []
        for i in range(N):
            cx = padding_x + i * (card_w + gap_x)
            positions.append((cx, top_y, card_w, card_h))
    else:
        # Two rows layout
        row1_count = (N + 1) // 2
        row2_count = N - row1_count
        card_h = 220
        row1_y = 88
        row2_y = row1_y + card_h + gap_y

        card_w1 = (W - padding_x * 2 - (row1_count - 1) * gap_x) // row1_count
        card_w2 = (W - padding_x * 2 - (row2_count - 1) * gap_x) // row2_count
        uniform_card_w = min(card_w1, card_w2)

        positions = []
        # Row 1
        total_w1 = row1_count * uniform_card_w + (row1_count - 1) * gap_x
        start_x1 = (W - total_w1) // 2
        for i in range(row1_count):
            cx = start_x1 + i * (uniform_card_w + gap_x)
            positions.append((cx, row1_y, uniform_card_w, card_h))

        # Row 2
        total_w2 = row2_count * uniform_card_w + (row2_count - 1) * gap_x
        start_x2 = (W - total_w2) // 2
        for i in range(row2_count):
            cx = start_x2 + i * (uniform_card_w + gap_x)
            positions.append((cx, row2_y, uniform_card_w, card_h))

    # Render each candidate card
    for idx, (candidate, (cx, cy, cw, ch)) in enumerate(zip(candidates, positions)):
        order_num = idx + 1
        name = candidate.get("display_name") or candidate.get("first_name") or f"ID {candidate.get('user_id')}"
        coef = candidate.get("coef", 2.0)
        total_bets = candidate.get("total_bets", 0)

        # Card container with smooth fill and subtle border
        draw.rounded_rectangle(
            [(cx, cy), (cx + cw, cy + ch)],
            radius=18,
            fill=(25, 29, 38, 255),
            outline=(46, 52, 68, 255),
            width=2,
        )

        # Number badge (top-left)
        badge_text = f"#{order_num}"
        draw.rounded_rectangle(
            [(cx + 12, cy + 12), (cx + 46, cy + 34)],
            radius=8,
            fill=(36, 42, 56, 255),
            outline=(56, 65, 86, 255),
            width=1,
        )
        bb = draw.textbbox((0, 0), badge_text, font=font_badge)
        draw.text(
            (cx + 12 + (34 - (bb[2] - bb[0])) // 2, cy + 12 + (22 - (bb[3] - bb[1])) // 2 - bb[1]),
            badge_text,
            font=font_badge,
            fill=(220, 226, 238, 255),
        )

        # Multiplier pill (top-right)
        coef_str = f"x{coef:.1f}" if coef == round(coef, 1) else f"x{coef:.2f}"
        coef_pill_w = 52
        coef_pill_h = 22
        rx = cx + cw - coef_pill_w - 12
        ry = cy + 12
        draw.rounded_rectangle(
            [(rx, ry), (rx + coef_pill_w, ry + coef_pill_h)],
            radius=8,
            fill=accent_pill_bg,
            outline=accent_pill_border,
            width=1,
        )
        cb = draw.textbbox((0, 0), coef_str, font=font_coef)
        draw.text(
            (rx + (coef_pill_w - (cb[2] - cb[0])) // 2, ry + (coef_pill_h - (cb[3] - cb[1])) // 2 - cb[1]),
            coef_str,
            font=font_coef,
            fill=accent_color,
        )

        # Avatar
        ava_size = 80 if not two_rows else 64
        ava_y = cy + (46 if not two_rows else 38)
        ava_x = cx + (cw - ava_size) // 2

        # Outer avatar ring
        draw.ellipse(
            [(ava_x - 3, ava_y - 3), (ava_x + ava_size + 2, ava_y + ava_size + 2)],
            outline=ring_color,
            width=2,
        )

        # Avatar image or fallback initials
        avatar_bytes = candidate.get("avatar_bytes")
        if avatar_bytes:
            try:
                ava_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
                ava_img = ava_img.resize((ava_size, ava_size), Image.Resampling.LANCZOS)
                mask = create_circle_mask(ava_size)
                canvas.paste(ava_img, (ava_x, ava_y), mask=mask)
            except Exception:
                fallback_ava = _draw_initials_avatar(
                    ava_size, name, (38, 44, 58, 255), accent_color, font_initials
                )
                canvas.paste(fallback_ava, (ava_x, ava_y), mask=fallback_ava)
        else:
            fallback_ava = _draw_initials_avatar(
                ava_size, name, (38, 44, 58, 255), accent_color, font_initials
            )
            canvas.paste(fallback_ava, (ava_x, ava_y), mask=fallback_ava)

        # Candidate name (centered, truncated if needed)
        max_name_w = cw - 20
        clean_name = name
        while len(clean_name) > 3:
            nb = draw.textbbox((0, 0), clean_name, font=font_name)
            if nb[2] - nb[0] <= max_name_w:
                break
            clean_name = clean_name[:-2] + "…"
        nb = draw.textbbox((0, 0), clean_name, font=font_name)
        nw = nb[2] - nb[0]
        name_y = ava_y + ava_size + (14 if not two_rows else 10)
        draw.text(
            (cx + (cw - nw) // 2, name_y),
            clean_name,
            font=font_name,
            fill=(245, 248, 252, 255),
        )

        # Bet bank / stats pill
        bet_pill_h = 26 if not two_rows else 22
        bet_pill_w = min(cw - 24, 150)
        bx = cx + (cw - bet_pill_w) // 2
        by = name_y + (26 if not two_rows else 22)
        draw.rounded_rectangle(
            [(bx, by), (bx + bet_pill_w, by + bet_pill_h)],
            radius=8,
            fill=(32, 36, 48, 255),
            outline=(48, 54, 70, 255),
            width=1,
        )
        if total_bets > 0:
            bets_str = f"{total_bets:,}".replace(",", " ")
            bets_color = (255, 220, 110, 255) if is_day else (255, 150, 160, 255)
            coin_icon = get_emoji_icon("coin", 14 if two_rows else 16)
            bb = draw.textbbox((0, 0), bets_str, font=font_bets)
            bw = bb[2] - bb[0]
            bh = bb[3] - bb[1]
            if coin_icon:
                gap = 4
                c_size = 14 if two_rows else 16
                tot_w = bw + gap + c_size
                sx = bx + (bet_pill_w - tot_w) // 2
                ty = by + (bet_pill_h - bh) // 2 - bb[1]
                draw.text((sx, ty), bets_str, font=font_bets, fill=bets_color)
                canvas.paste(coin_icon, (sx + bw + gap, by + (bet_pill_h - c_size) // 2), mask=coin_icon)
            else:
                draw.text(
                    (bx + (bet_pill_w - bw) // 2, by + (bet_pill_h - bh) // 2 - bb[1]),
                    bets_str,
                    font=font_bets,
                    fill=bets_color,
                )
        else:
            bets_str = "Ставок нет"
            bets_color = (130, 138, 155, 255)
            bb = draw.textbbox((0, 0), bets_str, font=font_bets)
            draw.text(
                (bx + (bet_pill_w - (bb[2] - bb[0])) // 2, by + (bet_pill_h - (bb[3] - bb[1])) // 2 - bb[1]),
                bets_str,
                font=font_bets,
                fill=bets_color,
            )

    # Footer status line
    pct_str = f"{round(N / max(1, total_participants) * 100)}%" if total_participants > 0 else "10%"
    footer_text = f"В пуле: {N} кандидатов ({pct_str} участников)   •   Мин. ставка: {min_bet} очков   •   Пул обновляется ежедневно"
    fb = draw.textbbox((0, 0), footer_text, font=font_footer)
    fw = fb[2] - fb[0]
    footer_y = H - 32
    draw.text(((W - fw) // 2, footer_y), footer_text, font=font_footer, fill=(120, 128, 145, 255))

    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
