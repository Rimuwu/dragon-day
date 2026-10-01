import io
import math
import os
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

from utils.leaderboard_card import get_emoji_icon


def create_circle_mask(size: int) -> Image.Image:
    """Creates a high-quality anti-aliased circular mask."""
    scale = 4
    dim = size * scale
    mask = Image.new("L", (dim, dim), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([(0, 0), (dim - 1, dim - 1)], fill=255)
    return mask.resize((size, size), Image.Resampling.LANCZOS)


# -------------------------------------------------------------------------
# Vector Drawing Helpers (Unified Red / Ruby Gothic Aesthetic)
# -------------------------------------------------------------------------

def draw_diamond_badge(draw: ImageDraw.ImageDraw, center: tuple[int, int], radius: int, outline_color=(235, 75, 90, 255), fill_color=(45, 18, 26, 230), width=2):
    """Draws an elegant rotated ruby diamond badge."""
    cx, cy = center
    pts = [
        (cx, cy - radius),
        (cx + radius, cy),
        (cx, cy + radius),
        (cx - radius, cy),
    ]
    draw.polygon(pts, fill=fill_color, outline=outline_color, width=width)
    inner_r = int(radius * 0.45)
    draw.line([(cx - inner_r, cy), (cx + inner_r, cy)], fill=outline_color, width=1)
    draw.line([(cx, cy - inner_r), (cx, cy + inner_r)], fill=outline_color, width=1)


def draw_star(draw: ImageDraw.ImageDraw, center: tuple[int, int], r_outer: int, r_inner: int, fill, outline=None, width=1):
    points = []
    for i in range(10):
        r = r_outer if i % 2 == 0 else r_inner
        angle = i * math.pi / 5 - math.pi / 2
        points.append((center[0] + r * math.cos(angle), center[1] + r * math.sin(angle)))
    draw.polygon(points, fill=fill, outline=outline, width=width)


def draw_watermark_sun(draw: ImageDraw.ImageDraw, center: tuple[int, int], r: int, color=(255, 255, 255, 18)):
    cx, cy = center
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=color, width=2)
    for i in range(8):
        angle = i * (math.pi / 4)
        x1 = cx + (r + 4) * math.cos(angle)
        y1 = cy + (r + 4) * math.sin(angle)
        x2 = cx + (r + 14) * math.cos(angle)
        y2 = cy + (r + 14) * math.sin(angle)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=2)


def draw_watermark_flame(draw: ImageDraw.ImageDraw, center: tuple[int, int], size: int, color=(255, 255, 255, 18)):
    cx, cy = center
    pts = [
        (cx, cy - size),
        (cx + size * 0.65, cy - size * 0.2),
        (cx + size * 0.85, cy + size * 0.6),
        (cx + size * 0.35, cy + size * 0.95),
        (cx, cy + size),
        (cx - size * 0.35, cy + size * 0.95),
        (cx - size * 0.85, cy + size * 0.6),
        (cx - size * 0.65, cy - size * 0.2),
    ]
    draw.polygon(pts, outline=color, width=2)


def draw_watermark_moon(canvas: Image.Image, center: tuple[int, int], r: int, color=(255, 255, 255, 18)):
    dim = r * 4
    temp = Image.new("RGBA", (dim, dim), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(temp)
    cx, cy = dim // 2, dim // 2
    tdraw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=color, width=2)
    
    offset_x = int(r * 0.55)
    offset_y = int(r * 0.15)
    cutout = Image.new("RGBA", (dim, dim), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(cutout)
    cdraw.ellipse([(cx - r + offset_x, cy - r - offset_y), (cx + r + offset_x, cy + r - offset_y)], fill=(0, 0, 0, 255))
    
    temp_alpha = temp.split()[3]
    cut_alpha = cutout.split()[3]
    final_alpha = Image.new("L", (dim, dim), 0)
    for y in range(dim):
        for x in range(dim):
            a1 = temp_alpha.getpixel((x, y))
            a2 = cut_alpha.getpixel((x, y))
            final_alpha.putpixel((x, y), 0 if a2 > 0 else a1)
    temp.putalpha(final_alpha)
    canvas.paste(temp, (center[0] - dim // 2, center[1] - dim // 2), temp)


def draw_watermark_dice(draw: ImageDraw.ImageDraw, center: tuple[int, int], size: int, color=(255, 255, 255, 18)):
    cx, cy = center
    x1, y1 = cx - size // 2, cy - size // 2
    x2, y2 = x1 + size, y1 + size
    draw.rounded_rectangle([(x1, y1), (x2, y2)], radius=size // 4, outline=color, width=2)
    pr = max(2, size // 10)
    pips = [
        (cx, cy),
        (x1 + size // 4, y1 + size // 4),
        (x2 - size // 4, y1 + size // 4),
        (x1 + size // 4, y2 - size // 4),
        (x2 - size // 4, y2 - size // 4),
    ]
    for px, py in pips:
        draw.ellipse([(px - pr, py - pr), (px + pr, py + pr)], fill=color)


def draw_checkmark(draw: ImageDraw.ImageDraw, center: tuple[int, int], size: int, color, width=3):
    cx, cy = center
    pts = [
        (cx - size * 0.6, cy),
        (cx - size * 0.1, cy + size * 0.5),
        (cx + size * 0.6, cy - size * 0.5),
    ]
    draw.line(pts, fill=color, width=width, joint="curve")


def format_streak_dates(count: int, start_date: str | None, end_date: str | None) -> tuple[str, str]:
    if not count or count <= 0:
        return "0 побед", "Серий пока нет"

    if count % 10 == 1 and count % 100 != 11:
        streak_str = f"{count} победа"
    elif 2 <= count % 10 <= 4 and not (12 <= count % 100 <= 14):
        streak_str = f"{count} победы"
    else:
        streak_str = f"{count} побед"

    def _fmt(d: str) -> str:
        try:
            parts = d.split("-")
            if len(parts) == 3:
                return f"{parts[2]}.{parts[1]}.{parts[0][2:]}"
        except Exception:
            pass
        return d

    if not start_date and not end_date:
        dates_str = "Период не зафиксирован"
    elif start_date and (not end_date or start_date == end_date):
        dates_str = f"Дата: {_fmt(start_date)}"
    else:
        dates_str = f"Период: {_fmt(start_date)} — {_fmt(end_date)}"

    return streak_str, dates_str


def _plural_wins(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "победа"
    elif 2 <= count % 10 <= 4 and not (12 <= count % 100 <= 14):
        return "победы"
    return "побед"


# -------------------------------------------------------------------------
# Prefab Cache System
# -------------------------------------------------------------------------
_PREFAB_CACHE: dict[tuple, tuple[float, Image.Image]] = {}
_MAX_PREFAB_CACHE = 40


def get_profile_base_prefab(
    user_id: int,
    avatar_bytes: bytes | None,
    display_name: str,
    username: str,
    points: int,
    bg_path: str,
    W: int = 960,
    H: int = 560,
) -> Image.Image:
    """
    Renders or fetches from cache the immutable base canvas and left profile column.
    (Avatar, halo rings, Name, ID, Points card - Rank removed as requested).
    """
    av_hash = hash(avatar_bytes) if avatar_bytes else 0
    cache_key = (user_id, display_name, username, points, bg_path, av_hash, W, H)

    # Check cache
    if cache_key in _PREFAB_CACHE:
        ts, cached_img = _PREFAB_CACHE[cache_key]
        if time.time() - ts < 300:  # 5 min TTL
            return cached_img.copy()

    # Create new base
    if os.path.exists(bg_path):
        try:
            base = Image.open(bg_path).convert("RGBA").resize((W, H), Image.Resampling.LANCZOS)
        except Exception:
            base = Image.new("RGBA", (W, H), (14, 17, 24, 255))
    else:
        base = Image.new("RGBA", (W, H), (14, 17, 24, 255))

    tint = Image.new("RGBA", (W, H), (10, 13, 19, 135))
    base = Image.alpha_composite(base, tint)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_name = ImageFont.truetype("fonts/bold.ttf", 26)
    font_card_title = ImageFont.truetype("fonts/bold.ttf", 15)
    font_points_num = ImageFont.truetype("fonts/bold.ttf", 32)
    font_bold_sub = ImageFont.truetype("fonts/bold.ttf", 13)
    font_body = ImageFont.truetype("fonts/default.ttf", 15)
    font_sub = ImageFont.truetype("fonts/default.ttf", 13)

    RED_ACCENT = (235, 75, 90, 255)
    CARD_BG = (17, 22, 29, 215)
    CARD_BG_SUB = (23, 29, 39, 225)
    CARD_BORDER = (255, 255, 255, 28)
    TEXT_WHITE = (248, 250, 252, 255)
    TEXT_MUTED = (145, 158, 172, 230)

    def draw_glass_panel(x, y, w, h, radius=18, bg=CARD_BG, border=CARD_BORDER, border_width=1):
        panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        pdraw = ImageDraw.Draw(panel)
        pdraw.rounded_rectangle(
            [(0, 0), (w - 1, h - 1)],
            radius=radius,
            fill=bg,
            outline=border,
            width=border_width,
        )
        overlay.paste(panel, (x, y), panel)

    # 1. Left panel: x=24, y=24, w=275, h=512
    lp_x, lp_y, lp_w, lp_h = 24, 24, 275, H - 48
    draw_glass_panel(lp_x, lp_y, lp_w, lp_h, radius=22, bg=(16, 20, 28, 230))

    # Avatar (145x145)
    av_size = 145
    av_x = lp_x + (lp_w - av_size) // 2
    av_y = lp_y + 35

    draw.ellipse([(av_x - 6, av_y - 6), (av_x + av_size + 6, av_y + av_size + 6)], outline=(235, 75, 90, 95), width=3)
    draw.ellipse([(av_x - 2, av_y - 2), (av_x + av_size + 2, av_y + av_size + 2)], outline=(255, 255, 255, 130), width=1)

    if avatar_bytes:
        try:
            av_raw = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            av_scaled = av_raw.resize((av_size, av_size), Image.Resampling.LANCZOS)
            mask = create_circle_mask(av_size)
            overlay.paste(av_scaled, (av_x, av_y), mask)
        except Exception:
            avatar_bytes = None

    if not avatar_bytes:
        draw.ellipse([(av_x, av_y), (av_x + av_size, av_y + av_size)], fill=(22, 27, 36, 255))
        crown_ico = get_emoji_icon("crown", 68)
        if crown_ico:
            overlay.paste(crown_ico, (av_x + (av_size - 68) // 2, av_y + (av_size - 68) // 2), mask=crown_ico)

    # Clean Name & Handle
    clean_name = display_name.strip()
    clean_user = username.strip()
    if clean_user and not clean_user.startswith("@"):
        clean_user = f"@{clean_user}"
    if clean_name.startswith("@"):
        clean_name = clean_name[1:]

    show_handle = clean_user if clean_user.lstrip("@").lower() != clean_name.lower() else ""

    # Dynamic pixel-width truncation to prevent any text overflow in the left panel (lp_w = 275)
    max_text_w = lp_w - 36
    name_display = clean_name
    nb = draw.textbbox((0, 0), name_display, font=font_name)
    if (nb[2] - nb[0]) > max_text_w:
        for i in range(len(clean_name) - 1, 0, -1):
            cand = clean_name[:i] + "…"
            cb = draw.textbbox((0, 0), cand, font=font_name)
            if (cb[2] - cb[0]) <= max_text_w:
                name_display = cand
                break
        else:
            name_display = clean_name[:8] + "…"

    nb = draw.textbbox((0, 0), name_display, font=font_name)
    nw = nb[2] - nb[0]
    draw.text((lp_x + (lp_w - nw) // 2, av_y + av_size + 20), name_display, font=font_name, fill=TEXT_WHITE)

    curr_y = av_y + av_size + 56
    if show_handle:
        handle_display = show_handle
        ub = draw.textbbox((0, 0), handle_display, font=font_body)
        if (ub[2] - ub[0]) > max_text_w:
            for i in range(len(show_handle) - 1, 0, -1):
                cand = show_handle[:i] + "…"
                cb = draw.textbbox((0, 0), cand, font=font_body)
                if (cb[2] - cb[0]) <= max_text_w:
                    handle_display = cand
                    break
            else:
                handle_display = show_handle[:10] + "…"
        ub = draw.textbbox((0, 0), handle_display, font=font_body)
        uw = ub[2] - ub[0]
        draw.text((lp_x + (lp_w - uw) // 2, curr_y), handle_display, font=font_body, fill=TEXT_MUTED)
        curr_y += 24

    id_str = f"ID: {user_id}"
    ib = draw.textbbox((0, 0), id_str, font=font_sub)
    iw = ib[2] - ib[0]
    draw.text((lp_x + (lp_w - iw) // 2, curr_y), id_str, font=font_sub, fill=(120, 132, 148, 220))

    # Single prominent bottom sub-card: "Очки"
    sub_w = lp_w - 28
    sub_h = 88
    sub_y = lp_y + lp_h - sub_h - 18

    draw_glass_panel(lp_x + 14, sub_y, sub_w, sub_h, radius=18, bg=CARD_BG_SUB)
    
    # Coin badge on left of points card
    draw.ellipse([(lp_x + 24, sub_y + (sub_h - 48) // 2), (lp_x + 72, sub_y + (sub_h + 48) // 2)], fill=(34, 24, 28, 220), outline=(235, 75, 90, 80), width=1)
    coin_icon = get_emoji_icon("coin", 36)
    if coin_icon:
        overlay.paste(coin_icon, (lp_x + 30, sub_y + (sub_h - 36) // 2), mask=coin_icon)

    draw.text((lp_x + 82, sub_y + 16), "ОЧКИ ДРАКОНА", font=font_card_title, fill=RED_ACCENT)
    pts_str = f"{points:,}".replace(",", " ")
    draw.text((lp_x + 82, sub_y + 40), pts_str, font=font_points_num, fill=TEXT_WHITE)

    prefab_result = Image.alpha_composite(base, overlay)

    # Store in cache
    if len(_PREFAB_CACHE) >= _MAX_PREFAB_CACHE:
        _PREFAB_CACHE.pop(next(iter(_PREFAB_CACHE)))
    _PREFAB_CACHE[cache_key] = (time.time(), prefab_result)

    return prefab_result.copy()


# -------------------------------------------------------------------------
# Multi-Page Profile Card Renderer (Spacious, Large Fonts, High Contrast)
# -------------------------------------------------------------------------

def render_profile_card(
    avatar_bytes: bytes | None,
    user_data: dict,
    bg_path: str = "images/profile_bg.png",
    page: str = "wins",
) -> io.BytesIO:
    """
    Renders a spacious, high-contrast profile card partitioned into tabs ('wins', 'bets', 'streaks').
    Uses the pre-rendered base prefab for instant execution and large, readable widgets.
    """
    W, H = 960, 560

    # 1. Base Prefab with Avatar, Name, ID, and Points
    user_id = user_data.get("user_id", 0)
    display_name = user_data.get("display_name", "Игрок")
    username = user_data.get("username", "")
    points = user_data.get("points", 0)

    base = get_profile_base_prefab(user_id, avatar_bytes, display_name, username, points, bg_path, W, H)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Fonts for Right Section
    font_huge_num = ImageFont.truetype("fonts/bold.ttf", 54)
    font_large_num = ImageFont.truetype("fonts/bold.ttf", 36)
    font_title_bold = ImageFont.truetype("fonts/bold.ttf", 19)
    font_card_title = ImageFont.truetype("fonts/bold.ttf", 16)
    font_bold_sub = ImageFont.truetype("fonts/bold.ttf", 14)
    font_body = ImageFont.truetype("fonts/default.ttf", 16)
    font_sub = ImageFont.truetype("fonts/default.ttf", 14)

    RED_ACCENT = (235, 75, 90, 255)
    RED_TRACK = (40, 24, 30, 255)
    CARD_BG = (17, 22, 29, 215)
    CARD_BG_SUB = (23, 29, 39, 225)
    CARD_BORDER = (255, 255, 255, 28)
    TEXT_WHITE = (248, 250, 252, 255)
    TEXT_MUTED = (145, 158, 172, 230)
    WATERMARK_COLOR = (255, 255, 255, 16)

    def draw_glass_panel(x, y, w, h, radius=18, bg=CARD_BG, border=CARD_BORDER, border_width=1):
        panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        pdraw = ImageDraw.Draw(panel)
        pdraw.rounded_rectangle(
            [(0, 0), (w - 1, h - 1)],
            radius=radius,
            fill=bg,
            outline=border,
            width=border_width,
        )
        overlay.paste(panel, (x, y), panel)

    # Data
    wins_day = user_data.get("wins_day", 0)
    wins_evil = user_data.get("wins_evil", 0)
    wins_sleepy = user_data.get("wins_sleepy", 0)
    total_wins = wins_day + wins_evil + wins_sleepy

    bets_played = user_data.get("bets_played", 0)
    bets_won = user_data.get("bets_won", 0)
    winrate = round((bets_won / bets_played * 100)) if bets_played > 0 else 0
    open_bets = user_data.get("open_bets", 0)

    # Right Area Boundaries
    r_x = 320
    r_y = 24
    r_w = W - 24 - r_x  # 616px
    r_h = H - 48        # 512px

    # =========================================================================
    # PAGE 1: WINS (🏆 Победы драконов)
    # =========================================================================
    if page == "wins":
        top_h = 130
        draw_glass_panel(r_x, r_y, r_w, top_h, radius=20)

        crown_ico = get_emoji_icon("crown", 56)
        if crown_ico:
            overlay.paste(crown_ico, (r_x + 26, r_y + (top_h - 56) // 2), mask=crown_ico)

        draw.text((r_x + 98, r_y + 24), "ВСЕГО ПОБЕД", font=font_title_bold, fill=RED_ACCENT)
        tot_text = f"{total_wins} {_plural_wins(total_wins)}"
        draw.text((r_x + 98, r_y + 54), tot_text, font=font_huge_num, fill=TEXT_WHITE)

        # Right side breakdown with emoji icons
        breakdown_items = [
            ("День: ", str(wins_day), "sun", r_y + 28),
            ("Злой: ", str(wins_evil), "evil", r_y + 54),
            ("Ночь: ", str(wins_sleepy), "sleepy", r_y + 80),
        ]
        for label, val_s, ico_name, item_y in breakdown_items:
            draw.text((r_x + r_w - 180, item_y), label + val_s, font=font_body, fill=TEXT_WHITE)
            tb = draw.textbbox((0, 0), label + val_s, font=font_body)
            tw = tb[2] - tb[0]
            ico = get_emoji_icon(ico_name, 16)
            if ico:
                overlay.paste(ico, (r_x + r_w - 180 + tw + 6, item_y + 1), mask=ico)

        # 3 Stacked Dragon Cards (Large, prominent, high readability)
        card_h = 110
        gap = 14
        c_y = r_y + top_h + 16

        dragons_data = [
            ("ДРАКОН ДНЯ", f"{wins_day} {_plural_wins(wins_day)}", "Солнечный орден стаи", "sun"),
            ("ЗЛОЙ ДРАКОН", f"{wins_evil} {_plural_wins(wins_evil)}", "Пламя ночного гнева", "evil"),
            ("НОЧНОЙ ДРАКОН", f"{wins_sleepy} {_plural_wins(wins_sleepy)}", "Сонные сокровища рассвета", "sleepy"),
        ]

        for title, count_text, desc, ico_name in dragons_data:
            draw_glass_panel(r_x, c_y, r_w, card_h, radius=18)

            d_ico = get_emoji_icon(ico_name, 44)
            if d_ico:
                overlay.paste(d_ico, (r_x + 24, c_y + (card_h - 44) // 2), mask=d_ico)

            draw.text((r_x + 84, c_y + 26), title, font=font_card_title, fill=RED_ACCENT)
            draw.text((r_x + 84, c_y + 58), desc, font=font_sub, fill=TEXT_MUTED)

            # Huge number on right
            vb = draw.textbbox((0, 0), count_text, font=font_large_num)
            vw = vb[2] - vb[0]
            draw.text((r_x + r_w - 28 - vw, c_y + 36), count_text, font=font_large_num, fill=TEXT_WHITE)

            c_y += card_h + gap

    # =========================================================================
    # PAGE 2: BETS (🎲 Ставки и азарт)
    # =========================================================================
    elif page == "bets":
        top_h = 165
        draw_glass_panel(r_x, r_y, r_w, top_h, radius=20)

        draw_watermark_dice(draw, (r_x + 75, r_y + top_h // 2 - 12), 65, color=WATERMARK_COLOR)

        draw.text((r_x + 160, r_y + 24), "ВИНРЕЙТ СТАВОК", font=font_title_bold, fill=RED_ACCENT)
        win_str = f"{winrate}%"
        draw.text((r_x + 160, r_y + 50), win_str, font=font_huge_num, fill=TEXT_WHITE)

        draw.text((r_x + r_w - 240, r_y + 32), f"Выиграно: {bets_won} из {bets_played}", font=font_body, fill=TEXT_WHITE)
        draw.text((r_x + r_w - 240, r_y + 60), f"Открыто сегодня: {open_bets}", font=font_body, fill=TEXT_MUTED)

        # Full width red progress bar
        bar_x = r_x + 40
        bar_w = r_w - 80
        bar_y = r_y + top_h - 32
        draw.rounded_rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + 8)], radius=4, fill=RED_TRACK)
        fill_w = int(bar_w * (winrate / 100.0))
        if fill_w > 0:
            draw.rounded_rectangle([(bar_x, bar_y), (bar_x + fill_w, bar_y + 8)], radius=4, fill=RED_ACCENT)

        # Bottom 2 Large Stat Cards
        c_y = r_y + top_h + 16
        c_h = r_h - top_h - 16
        c_w = (r_w - 16) // 2

        # Card 1: Сыграно ставок
        c1_x = r_x
        draw_glass_panel(c1_x, c_y, c_w, c_h, radius=18)
        draw_watermark_dice(draw, (c1_x + c_w - 55, c_y + 55), 45, color=WATERMARK_COLOR)
        draw.text((c1_x + 24, c_y + 24), "СЫГРАНО СТАВОК", font=font_card_title, fill=RED_ACCENT)
        bp_str = str(bets_played)
        draw.text((c1_x + 24, c_y + 60), bp_str, font=font_huge_num, fill=TEXT_WHITE)
        draw.text((c1_x + 24, c_y + 145), f"Успешных ставок: {bets_won}", font=font_body, fill=TEXT_MUTED)
        draw.text((c1_x + 24, c_y + 180), f"Проигранных: {max(0, bets_played - bets_won)}", font=font_body, fill=TEXT_MUTED)
        draw.line([(c1_x + 24, c_y + c_h - 35), (c1_x + c_w - 24, c_y + c_h - 35)], fill=RED_ACCENT, width=2)

        # Card 2: Открытые ставки
        c2_x = r_x + c_w + 16
        draw_glass_panel(c2_x, c_y, c_w, c_h, radius=18)
        draw_watermark_dice(draw, (c2_x + c_w - 55, c_y + 55), 45, color=WATERMARK_COLOR)
        draw.text((c2_x + 24, c_y + 24), "ОТКРЫТЫЕ СТАВКИ", font=font_card_title, fill=RED_ACCENT)
        ob_str = str(open_bets)
        draw.text((c2_x + 24, c_y + 60), ob_str, font=font_huge_num, fill=TEXT_WHITE)
        draw.text((c2_x + 24, c_y + 145), "Сделано ставок сегодня", font=font_body, fill=TEXT_MUTED)
        draw.text((c2_x + 24, c_y + 180), "Ожидают подведения итогов", font=font_sub, fill=TEXT_MUTED)
        draw.line([(c2_x + 24, c_y + c_h - 35), (c2_x + c_w - 24, c_y + c_h - 35)], fill=RED_ACCENT, width=2)

    # =========================================================================
    # PAGE: DUELS (⚔️ Дуэли на кубиках)
    # =========================================================================
    elif page == "duels":
        duels_played = user_data.get("duels_played", 0)
        duels_won = user_data.get("duels_won", 0)
        duels_points_won = user_data.get("duels_points_won", user_data.get("duel_points_won", 0))
        duel_winrate = round((duels_won / duels_played * 100)) if duels_played > 0 else 0

        top_h = 165
        draw_glass_panel(r_x, r_y, r_w, top_h, radius=20)
        draw_watermark_dice(draw, (r_x + 75, r_y + top_h // 2 - 12), 65, color=WATERMARK_COLOR)

        draw.text((r_x + 160, r_y + 24), "ВИНРЕЙТ В ДУЭЛЯХ", font=font_title_bold, fill=RED_ACCENT)
        win_str = f"{duel_winrate}%"
        draw.text((r_x + 160, r_y + 50), win_str, font=font_huge_num, fill=TEXT_WHITE)

        draw.text((r_x + r_w - 240, r_y + 32), f"Побед: {duels_won} из {duels_played}", font=font_body, fill=TEXT_WHITE)
        net_str = f"+{duels_points_won:,}" if duels_points_won >= 0 else f"{duels_points_won:,}"
        net_full = f"Баланс: {net_str.replace(',', ' ')}"
        draw.text((r_x + r_w - 240, r_y + 60), net_full, font=font_body, fill=TEXT_MUTED)
        nb = draw.textbbox((0, 0), net_full, font=font_body)
        nw = nb[2] - nb[0]
        c_ico = get_emoji_icon("coin", 16)
        if c_ico:
            overlay.paste(c_ico, (r_x + r_w - 240 + nw + 6, r_y + 61), mask=c_ico)

        # Progress bar
        bar_x = r_x + 40
        bar_w = r_w - 80
        bar_y = r_y + top_h - 32
        draw.rounded_rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + 8)], radius=4, fill=RED_TRACK)
        fill_w = int(bar_w * (duel_winrate / 100.0))
        if fill_w > 0:
            draw.rounded_rectangle([(bar_x, bar_y), (bar_x + fill_w, bar_y + 8)], radius=4, fill=RED_ACCENT)

        # Bottom 2 Large Stat Cards
        c_y = r_y + top_h + 16
        c_h = r_h - top_h - 16
        c_w = (r_w - 16) // 2

        # Card 1: Сыграно дуэлей
        c1_x = r_x
        draw_glass_panel(c1_x, c_y, c_w, c_h, radius=18)
        draw_watermark_dice(draw, (c1_x + c_w - 55, c_y + 55), 45, color=WATERMARK_COLOR)
        draw.text((c1_x + 24, c_y + 24), "СЫГРАНО ДУЭЛЕЙ", font=font_card_title, fill=RED_ACCENT)
        draw.text((c1_x + 24, c_y + 60), str(duels_played), font=font_huge_num, fill=TEXT_WHITE)
        draw.text((c1_x + 24, c_y + 145), f"Выиграно дуэлей: {duels_won}", font=font_body, fill=TEXT_MUTED)
        draw.text((c1_x + 24, c_y + 180), f"Поражений / ничьих: {max(0, duels_played - duels_won)}", font=font_body, fill=TEXT_MUTED)
        draw.line([(c1_x + 24, c_y + c_h - 35), (c1_x + c_w - 24, c_y + c_h - 35)], fill=RED_ACCENT, width=2)

        # Card 2: Очки с дуэлей
        c2_x = r_x + c_w + 16
        draw_glass_panel(c2_x, c_y, c_w, c_h, radius=18)
        draw_watermark_sun(draw, (c2_x + c_w - 55, c_y + 55), 35, color=WATERMARK_COLOR)
        draw.text((c2_x + 24, c_y + 24), "ОЧКИ С ДУЭЛЕЙ", font=font_card_title, fill=RED_ACCENT)
        pts_won_str = f"{duels_points_won:,}".replace(",", " ")
        draw.text((c2_x + 24, c_y + 60), pts_won_str, font=font_huge_num, fill=TEXT_WHITE)
        draw.text((c2_x + 24, c_y + 145), "Чистая прибыль в дуэлях", font=font_body, fill=TEXT_MUTED)
        draw.text((c2_x + 24, c_y + 180), "Учитывает все победы и ставки", font=font_sub, fill=TEXT_MUTED)
        draw.line([(c2_x + 24, c_y + c_h - 35), (c2_x + c_w - 24, c_y + c_h - 35)], fill=RED_ACCENT, width=2)

    # =========================================================================
    # PAGE: LOTTERY (🎟️ Королевская лотерея)
    # =========================================================================
    elif page == "lottery":
        lottery_played = user_data.get("lottery_played", 0)
        lottery_won = user_data.get("lottery_won", 0)
        lottery_points_won = user_data.get("lottery_points_won", 0)
        lottery_winrate = round((lottery_won / lottery_played * 100)) if lottery_played > 0 else 0

        top_h = 165
        draw_glass_panel(r_x, r_y, r_w, top_h, radius=20)
        draw_watermark_flame(draw, (r_x + 75, r_y + top_h // 2 - 12), 45, color=WATERMARK_COLOR)

        draw.text((r_x + 160, r_y + 24), "УДАЧА В ЛОТЕРЕЕ", font=font_title_bold, fill=RED_ACCENT)
        win_str = f"{lottery_winrate}%"
        draw.text((r_x + 160, r_y + 50), win_str, font=font_huge_num, fill=TEXT_WHITE)

        draw.text((r_x + r_w - 240, r_y + 32), f"Побед: {lottery_won} из {lottery_played}", font=font_body, fill=TEXT_WHITE)
        pts_net = f"+{lottery_points_won:,}" if lottery_points_won >= 0 else f"{lottery_points_won:,}"
        kush_full = f"Куш: {pts_net.replace(',', ' ')}"
        draw.text((r_x + r_w - 240, r_y + 60), kush_full, font=font_body, fill=TEXT_MUTED)
        kb = draw.textbbox((0, 0), kush_full, font=font_body)
        kw = kb[2] - kb[0]
        c_ico = get_emoji_icon("coin", 16)
        if c_ico:
            overlay.paste(c_ico, (r_x + r_w - 240 + kw + 6, r_y + 61), mask=c_ico)

        # Progress bar
        bar_x = r_x + 40
        bar_w = r_w - 80
        bar_y = r_y + top_h - 32
        draw.rounded_rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + 8)], radius=4, fill=RED_TRACK)
        fill_w = int(bar_w * (lottery_winrate / 100.0))
        if fill_w > 0:
            draw.rounded_rectangle([(bar_x, bar_y), (bar_x + fill_w, bar_y + 8)], radius=4, fill=RED_ACCENT)

        # Bottom 2 Large Stat Cards
        c_y = r_y + top_h + 16
        c_h = r_h - top_h - 16
        c_w = (r_w - 16) // 2

        # Card 1: Участий в лотерее
        c1_x = r_x
        draw_glass_panel(c1_x, c_y, c_w, c_h, radius=18)
        draw_watermark_sun(draw, (c1_x + c_w - 55, c_y + 55), 35, color=WATERMARK_COLOR)
        draw.text((c1_x + 24, c_y + 24), "СЫГРАНО ЛОТЕРЕЙ", font=font_card_title, fill=RED_ACCENT)
        draw.text((c1_x + 24, c_y + 60), str(lottery_played), font=font_huge_num, fill=TEXT_WHITE)
        draw.text((c1_x + 24, c_y + 145), f"Выиграно джекпотов: {lottery_won}", font=font_body, fill=TEXT_MUTED)
        draw.text((c1_x + 24, c_y + 180), f"Без выигрыша: {max(0, lottery_played - lottery_won)}", font=font_body, fill=TEXT_MUTED)
        draw.line([(c1_x + 24, c_y + c_h - 35), (c1_x + c_w - 24, c_y + c_h - 35)], fill=RED_ACCENT, width=2)

        # Card 2: Выиграно очков
        c2_x = r_x + c_w + 16
        draw_glass_panel(c2_x, c_y, c_w, c_h, radius=18)
        draw_watermark_flame(draw, (c2_x + c_w - 55, c_y + 55), 45, color=WATERMARK_COLOR)
        draw.text((c2_x + 24, c_y + 24), "ВЫИГРАННЫЙ КУШ", font=font_card_title, fill=RED_ACCENT)
        l_pts_str = f"{lottery_points_won:,}".replace(",", " ")
        draw.text((c2_x + 24, c_y + 60), l_pts_str, font=font_huge_num, fill=TEXT_WHITE)
        draw.text((c2_x + 24, c_y + 145), "Чистая прибыль в лотереях", font=font_body, fill=TEXT_MUTED)
        draw.text((c2_x + 24, c_y + 180), "Сумма полученных банков", font=font_sub, fill=TEXT_MUTED)
        draw.line([(c2_x + 24, c_y + c_h - 35), (c2_x + c_w - 24, c_y + c_h - 35)], fill=RED_ACCENT, width=2)

    # =========================================================================
    # PAGE 3: STREAKS (🔥 Рекорды и серии)
    # =========================================================================
    elif page == "streaks":
        day_streak_str, day_dates_str = format_streak_dates(
            user_data.get("max_streak_day", 0),
            user_data.get("max_streak_day_start"),
            user_data.get("max_streak_day_end"),
        )
        evil_streak_str, evil_dates_str = format_streak_dates(
            user_data.get("max_streak_evil", 0),
            user_data.get("max_streak_evil_start"),
            user_data.get("max_streak_evil_end"),
        )
        sleepy_streak_str, sleepy_dates_str = format_streak_dates(
            user_data.get("max_streak_sleepy", 0),
            user_data.get("max_streak_sleepy_start"),
            user_data.get("max_streak_sleepy_end"),
        )

        streaks = [
            ("ДРАКОН ДНЯ", user_data.get("max_streak_day", 0), day_dates_str),
            ("ЗЛОЙ ДРАКОН", user_data.get("max_streak_evil", 0), evil_dates_str),
            ("НОЧНОЙ ДРАКОН", user_data.get("max_streak_sleepy", 0), sleepy_dates_str),
        ]

        # Top title card
        top_h = 60
        draw_glass_panel(r_x, r_y, r_w, top_h, radius=18)
        draw.text((r_x + 28, r_y + 18), "РЕКОРДНЫЕ СЕРИИ ПОБЕД", font=font_title_bold, fill=RED_ACCENT)

        # 3 Stacked Cards
        card_h = 110
        gap = 14
        c_y = r_y + top_h + 14

        for title, count, dates_txt in streaks:
            draw_glass_panel(r_x, c_y, r_w, card_h, radius=18)

            has_streak = count > 0
            cb_size = 32
            cb_x = r_x + 24
            cb_cy = c_y + card_h // 2 - cb_size // 2

            if has_streak:
                draw.rounded_rectangle([(cb_x, cb_cy), (cb_x + cb_size, cb_cy + cb_size)], radius=8, fill=RED_ACCENT)
                draw_checkmark(draw, (cb_x + cb_size // 2, cb_cy + cb_size // 2), 8, TEXT_WHITE, width=3)
            else:
                draw.rounded_rectangle([(cb_x, cb_cy), (cb_x + cb_size, cb_cy + cb_size)], radius=8, fill=(28, 33, 44, 200), outline=CARD_BORDER, width=2)

            # Title & Dates
            draw.text((r_x + 74, c_y + 26), title, font=font_card_title, fill=TEXT_WHITE)
            draw.text((r_x + 74, c_y + 58), dates_txt, font=font_body, fill=TEXT_MUTED)

            # Value on right: e.g. "2 победы" (huge 36pt) + "подряд"
            count_str = f"{count} {_plural_wins(count)}" if count > 0 else "0 побед"
            sub_streak = "подряд" if count > 0 else "нет серий"

            vb = draw.textbbox((0, 0), count_str, font=font_large_num)
            vw = vb[2] - vb[0]
            val_x = r_x + r_w - 28 - vw
            draw.text((val_x, c_y + 22), count_str, font=font_large_num, fill=RED_ACCENT if has_streak else TEXT_MUTED)
            
            sb = draw.textbbox((0, 0), sub_streak, font=font_sub)
            sw = sb[2] - sb[0]
            draw.text((r_x + r_w - 28 - sw, c_y + 66), sub_streak, font=font_sub, fill=RED_ACCENT if has_streak else TEXT_MUTED)

            c_y += card_h + gap

        # Bottom summary line
        max_overall = max(
            user_data.get("max_streak_day", 0),
            user_data.get("max_streak_evil", 0),
            user_data.get("max_streak_sleepy", 0),
        )
        active_count = sum(1 for _, count, _ in streaks if count > 0)

        bot_card_h = 55
        draw_glass_panel(r_x, c_y, r_w, bot_card_h, radius=16)
        draw.text((r_x + 28, c_y + 18), f"Рекорд серий: {max_overall} дн.", font=font_card_title, fill=TEXT_WHITE)
        draw.text((r_x + r_w - 180, c_y + 18), f"Категорий: {active_count} из 3", font=font_body, fill=RED_ACCENT)

    # =========================================================================
    # PAGE: DAILY (🎯 Ежедневные шансы и серии максимумов)
    # =========================================================================
    elif page == "daily":
        daily_games = user_data.get("daily_games", {})
        cur_streak = user_data.get("current_streak_daily_max", 0)
        max_streak = user_data.get("max_streak_daily_max", 0)
        played_count = len(daily_games)

        font_stat_num = ImageFont.truetype("fonts/bold.ttf", 38)

        # Top Banner: Серия максимумов (Джекпот-стрик)
        top_h = 136
        draw_glass_panel(r_x, r_y, r_w, top_h, radius=20)

        # Clean fire icon on left
        fire_icon = get_emoji_icon("fire", 46)
        if fire_icon:
            overlay.paste(fire_icon, (r_x + 22, r_y + 24), mask=fire_icon)

        draw.text((r_x + 78, r_y + 18), "СЕРИЯ МАКСИМУМОВ", font=font_title_bold, fill=RED_ACCENT)
        streak_str = f"{cur_streak} дн."
        draw.text((r_x + 78, r_y + 44), streak_str, font=font_stat_num, fill=TEXT_WHITE)

        sb = draw.textbbox((0, 0), streak_str, font=font_stat_num)
        sw = sb[2] - sb[0]
        draw.text((r_x + 78 + sw + 12, r_y + 58), "подряд без сброса", font=font_sub, fill=TEXT_MUTED)

        # Right side stats (right-aligned to avoid any title overlap)
        rec_text = f"Рекорд: {max_streak} дн. подряд"
        chances_text = f"Шансы: {played_count} из 4"

        rb = draw.textbbox((0, 0), rec_text, font=font_body)
        rw = rb[2] - rb[0]
        draw.text((r_x + r_w - 24 - rw, r_y + 20), rec_text, font=font_body, fill=TEXT_WHITE)

        cb = draw.textbbox((0, 0), chances_text, font=font_body)
        cw = cb[2] - cb[0]
        draw.text((r_x + r_w - 24 - cw, r_y + 48), chances_text, font=font_body, fill=TEXT_MUTED)

        # Progress bar of chances used today with 20px breathing room below text
        bar_x = r_x + 24
        bar_w = r_w - 48
        bar_y = r_y + 104
        draw.rounded_rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + 8)], radius=4, fill=RED_TRACK)
        fill_w = int(bar_w * (min(4, played_count) / 4.0))
        if fill_w > 0:
            draw.rounded_rectangle([(bar_x, bar_y), (bar_x + fill_w, bar_y + 8)], radius=4, fill=RED_ACCENT)

        # 4 Game Cards (2x2 Grid)
        c_y = r_y + top_h + 14
        c_w = (r_w - 14) // 2
        c_h = (r_h - top_h - 28) // 2

        games_def = [
            ("dice", "КУБИК", "/roll", 6),
            ("basket", "БАСКЕТБОЛ", "/basket", 5),
            ("bowling", "БОУЛИНГ", "/bowling", 6),
            ("football", "ФУТБОЛ", "/football", 5),
        ]

        for i, (g_key, g_title, g_cmd, max_val) in enumerate(games_def):
            col = i % 2
            row = i // 2
            gx = r_x + col * (c_w + 14)
            gy = c_y + row * (c_h + 14)

            draw_glass_panel(gx, gy, c_w, c_h, radius=18)

            g_info = daily_games.get(g_key)
            is_played = g_info is not None

            # Title & Command
            draw.text((gx + 22, gy + 18), g_title, font=font_card_title, fill=RED_ACCENT)
            draw.text((gx + 22, gy + 40), g_cmd, font=font_bold_sub, fill=TEXT_MUTED)

            if is_played:
                val = g_info.get("value", 0)
                pts = g_info.get("points", 0)
                is_max = g_info.get("is_max", False)
                pts_str = f"+{pts}" if pts > 0 else str(pts)

                # Badge
                badge_text = "ДЖЕКПОТ" if is_max else "СЫГРАНО"
                bb = draw.textbbox((0, 0), badge_text, font=font_bold_sub)
                bw = bb[2] - bb[0] + 16
                bh = 22
                bx = gx + c_w - bw - 18
                by = gy + 18
                b_color = (235, 75, 90, 255) if is_max else (52, 211, 153, 255)
                draw.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=6, outline=b_color, width=1)
                draw.text((bx + 8, by + 3), badge_text, font=font_bold_sub, fill=b_color)

                # Big Score
                draw.text((gx + 22, gy + 68), f"{val} / {max_val}", font=font_large_num, fill=TEXT_WHITE)
                draw.text((gx + 22, gy + 118), f"Очки: {pts_str}", font=font_body, fill=RED_ACCENT if is_max else TEXT_MUTED)
                draw.line([(gx + 22, gy + c_h - 18), (gx + c_w - 22, gy + c_h - 18)], fill=b_color, width=2)
            else:
                # Available
                badge_text = "ДОСТУПНО"
                bb = draw.textbbox((0, 0), badge_text, font=font_bold_sub)
                bw = bb[2] - bb[0] + 16
                bh = 22
                bx = gx + c_w - bw - 18
                by = gy + 18
                b_color = (74, 222, 128, 220)
                draw.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=6, outline=b_color, width=1)
                draw.text((bx + 8, by + 3), badge_text, font=font_bold_sub, fill=b_color)

                draw.text((gx + 22, gy + 68), f"— / {max_val}", font=font_large_num, fill=(120, 135, 150, 200))
                draw.text((gx + 22, gy + 118), "Ждет броска!", font=font_body, fill=TEXT_MUTED)
                draw.line([(gx + 22, gy + c_h - 18), (gx + c_w - 22, gy + c_h - 18)], fill=(74, 222, 128, 140), width=1)

    # -------------------------------------------------------------------------
    # Composite and Return
    # -------------------------------------------------------------------------
    final_img = Image.alpha_composite(base, overlay)

    output = io.BytesIO()
    final_img.convert("RGB").save(output, format="PNG", optimize=True)
    output.seek(0)
    return output
