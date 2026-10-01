import io
import math
import os
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

from utils.leaderboard_card import get_emoji_icon


# -------------------------------------------------------------------------
# Global Font Cache & Pre-warmed Mask
# -------------------------------------------------------------------------
_FONTS: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def get_font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    key = (weight, size)
    if key not in _FONTS:
        path = "fonts/bold.ttf" if weight == "bold" else "fonts/default.ttf"
        try:
            _FONTS[key] = ImageFont.truetype(path, size)
        except Exception:
            _FONTS[key] = ImageFont.load_default()
    return _FONTS[key]


def create_circle_mask(size: int) -> Image.Image:
    """Creates a high-quality anti-aliased circular mask."""
    scale = 4
    dim = size * scale
    mask = Image.new("L", (dim, dim), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([(0, 0), (dim - 1, dim - 1)], fill=255)
    return mask.resize((size, size), Image.Resampling.LANCZOS)


_AVATAR_MASK_145 = create_circle_mask(145)
_AVATAR_PROCESSED_CACHE: dict[int, Image.Image] = {}


def get_processed_avatar(avatar_bytes: bytes, size: int = 145) -> Image.Image | None:
    av_hash = hash(avatar_bytes)
    if av_hash in _AVATAR_PROCESSED_CACHE:
        return _AVATAR_PROCESSED_CACHE[av_hash]

    try:
        raw_av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        scaled_av = raw_av.resize((size, size), Image.Resampling.LANCZOS)
        mask = _AVATAR_MASK_145 if size == 145 else create_circle_mask(size)
        
        result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        result.paste(scaled_av, (0, 0), mask)
        
        if len(_AVATAR_PROCESSED_CACHE) > 50:
            _AVATAR_PROCESSED_CACHE.pop(next(iter(_AVATAR_PROCESSED_CACHE)))
        _AVATAR_PROCESSED_CACHE[av_hash] = result
        return result
    except Exception:
        return None


# -------------------------------------------------------------------------
# Vector Drawing Helpers
# -------------------------------------------------------------------------

def draw_watermark_sun(draw: ImageDraw.ImageDraw, center: tuple[int, int], r: int, color=(255, 255, 255, 16)):
    cx, cy = center
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=color, width=2)
    for i in range(8):
        angle = i * (math.pi / 4)
        x1 = cx + (r + 4) * math.cos(angle)
        y1 = cy + (r + 4) * math.sin(angle)
        x2 = cx + (r + 14) * math.cos(angle)
        y2 = cy + (r + 14) * math.sin(angle)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=2)


def draw_watermark_flame(draw: ImageDraw.ImageDraw, center: tuple[int, int], size: int, color=(255, 255, 255, 16)):
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


def draw_watermark_dice(draw: ImageDraw.ImageDraw, center: tuple[int, int], size: int, color=(255, 255, 255, 16)):
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
# Design Tokens
# -------------------------------------------------------------------------
W, H = 960, 560
RED_ACCENT = (235, 75, 90, 255)
RED_TRACK = (40, 24, 30, 255)
CARD_BG = (17, 22, 29, 215)
CARD_BG_SUB = (23, 29, 39, 225)
CARD_BORDER = (255, 255, 255, 28)
TEXT_WHITE = (248, 250, 252, 255)
TEXT_MUTED = (145, 158, 172, 230)
WATERMARK_COLOR = (255, 255, 255, 16)

lp_x, lp_y, lp_w, lp_h = 24, 24, 275, H - 48
r_x, r_y, r_w, r_h = 320, 24, W - 24 - 320, H - 48


def _draw_glass_panel(overlay: Image.Image, x: int, y: int, w: int, h: int, radius=18, bg=CARD_BG, border=CARD_BORDER, border_width=1):
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


# -------------------------------------------------------------------------
# Static Template Generator & Cache
# -------------------------------------------------------------------------
_PAGE_STATIC_TEMPLATES: dict[tuple[str, str], Image.Image] = {}


def _build_page_static_template(page: str, bg_path: str = "images/profile_bg.png") -> Image.Image:
    """
    Builds the static background, left panel frame, and right tab panels.
    Everything here is 100% static and invariant between users!
    """
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

    # 1. Left Panel (Immutable layout)
    _draw_glass_panel(overlay, lp_x, lp_y, lp_w, lp_h, radius=22, bg=(16, 20, 28, 230))

    # Avatar ring borders
    av_size = 145
    av_x = lp_x + (lp_w - av_size) // 2
    av_y = lp_y + 35
    draw.ellipse([(av_x - 6, av_y - 6), (av_x + av_size + 6, av_y + av_size + 6)], outline=(235, 75, 90, 95), width=3)
    draw.ellipse([(av_x - 2, av_y - 2), (av_x + av_size + 2, av_y + av_size + 2)], outline=(255, 255, 255, 130), width=1)
    draw.ellipse([(av_x, av_y), (av_x + av_size, av_y + av_size)], fill=(22, 27, 36, 255))

    # Points sub-card frame
    sub_w = lp_w - 28
    sub_h = 88
    sub_y = lp_y + lp_h - sub_h - 18
    _draw_glass_panel(overlay, lp_x + 14, sub_y, sub_w, sub_h, radius=18, bg=CARD_BG_SUB)
    draw.ellipse([(lp_x + 24, sub_y + (sub_h - 48) // 2), (lp_x + 72, sub_y + (sub_h + 48) // 2)], fill=(34, 24, 28, 220), outline=(235, 75, 90, 80), width=1)
    
    coin_icon = get_emoji_icon("coin", 36)
    if coin_icon:
        overlay.paste(coin_icon, (lp_x + 30, sub_y + (sub_h - 36) // 2), mask=coin_icon)
    draw.text((lp_x + 82, sub_y + 16), "ОЧКИ ДРАКОНА", font=get_font("bold", 15), fill=RED_ACCENT)

    # 2. Right Panel Layout per Page
    if page == "wins":
        top_h = 130
        _draw_glass_panel(overlay, r_x, r_y, r_w, top_h, radius=20)
        crown_ico = get_emoji_icon("crown", 56)
        if crown_ico:
            overlay.paste(crown_ico, (r_x + 26, r_y + (top_h - 56) // 2), mask=crown_ico)
        draw.text((r_x + 98, r_y + 24), "ВСЕГО ПОБЕД", font=get_font("bold", 19), fill=RED_ACCENT)

        card_h = 110
        gap = 14
        c_y = r_y + top_h + 16
        dragons_data = [
            ("ДРАКОН ДНЯ", "Солнечный орден стаи", "sun"),
            ("ЗЛОЙ ДРАКОН", "Пламя ночного гнева", "evil"),
            ("НОЧНОЙ ДРАКОН", "Сонные сокровища рассвета", "sleepy"),
        ]
        for title, desc, ico_name in dragons_data:
            _draw_glass_panel(overlay, r_x, c_y, r_w, card_h, radius=18)
            d_ico = get_emoji_icon(ico_name, 44)
            if d_ico:
                overlay.paste(d_ico, (r_x + 24, c_y + (card_h - 44) // 2), mask=d_ico)
            draw.text((r_x + 84, c_y + 26), title, font=get_font("bold", 16), fill=RED_ACCENT)
            draw.text((r_x + 84, c_y + 58), desc, font=get_font("default", 14), fill=TEXT_MUTED)
            c_y += card_h + gap

    elif page == "bets":
        top_h = 165
        _draw_glass_panel(overlay, r_x, r_y, r_w, top_h, radius=20)
        draw_watermark_dice(draw, (r_x + 75, r_y + top_h // 2 - 12), 65, color=WATERMARK_COLOR)
        draw.text((r_x + 160, r_y + 24), "ВИНРЕЙТ СТАВОК", font=get_font("bold", 19), fill=RED_ACCENT)
        # Track bar
        bar_x = r_x + 40
        bar_w = r_w - 80
        bar_y = r_y + top_h - 32
        draw.rounded_rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + 8)], radius=4, fill=RED_TRACK)

        c_y = r_y + top_h + 16
        c_h = r_h - top_h - 16
        c_w = (r_w - 16) // 2

        # Card 1
        c1_x = r_x
        _draw_glass_panel(overlay, c1_x, c_y, c_w, c_h, radius=18)
        draw_watermark_dice(draw, (c1_x + c_w - 55, c_y + 55), 45, color=WATERMARK_COLOR)
        draw.text((c1_x + 24, c_y + 24), "СЫГРАНО СТАВОК", font=get_font("bold", 16), fill=RED_ACCENT)
        draw.line([(c1_x + 24, c_y + c_h - 35), (c1_x + c_w - 24, c_y + c_h - 35)], fill=RED_ACCENT, width=2)

        # Card 2
        c2_x = r_x + c_w + 16
        _draw_glass_panel(overlay, c2_x, c_y, c_w, c_h, radius=18)
        draw_watermark_dice(draw, (c2_x + c_w - 55, c_y + 55), 45, color=WATERMARK_COLOR)
        draw.text((c2_x + 24, c_y + 24), "ОТКРЫТЫЕ СТАВКИ", font=get_font("bold", 16), fill=RED_ACCENT)
        draw.text((c2_x + 24, c_y + 145), "Сделано ставок сегодня", font=get_font("default", 16), fill=TEXT_MUTED)
        draw.text((c2_x + 24, c_y + 180), "Ожидают подведения итогов", font=get_font("default", 14), fill=TEXT_MUTED)
        draw.line([(c2_x + 24, c_y + c_h - 35), (c2_x + c_w - 24, c_y + c_h - 35)], fill=RED_ACCENT, width=2)

    elif page == "duels":
        top_h = 165
        _draw_glass_panel(overlay, r_x, r_y, r_w, top_h, radius=20)
        draw_watermark_dice(draw, (r_x + 75, r_y + top_h // 2 - 12), 65, color=WATERMARK_COLOR)
        draw.text((r_x + 160, r_y + 24), "ВИНРЕЙТ В ДУЭЛЯХ", font=get_font("bold", 19), fill=RED_ACCENT)
        bar_x = r_x + 40
        bar_w = r_w - 80
        bar_y = r_y + top_h - 32
        draw.rounded_rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + 8)], radius=4, fill=RED_TRACK)

        c_y = r_y + top_h + 16
        c_h = r_h - top_h - 16
        c_w = (r_w - 16) // 2

        # Card 1
        c1_x = r_x
        _draw_glass_panel(overlay, c1_x, c_y, c_w, c_h, radius=18)
        draw_watermark_dice(draw, (c1_x + c_w - 55, c_y + 55), 45, color=WATERMARK_COLOR)
        draw.text((c1_x + 24, c_y + 24), "СЫГРАНО ДУЭЛЕЙ", font=get_font("bold", 16), fill=RED_ACCENT)
        draw.line([(c1_x + 24, c_y + c_h - 35), (c1_x + c_w - 24, c_y + c_h - 35)], fill=RED_ACCENT, width=2)

        # Card 2
        c2_x = r_x + c_w + 16
        _draw_glass_panel(overlay, c2_x, c_y, c_w, c_h, radius=18)
        draw_watermark_sun(draw, (c2_x + c_w - 55, c_y + 55), 35, color=WATERMARK_COLOR)
        draw.text((c2_x + 24, c_y + 24), "ОЧКИ С ДУЭЛЕЙ", font=get_font("bold", 16), fill=RED_ACCENT)
        draw.text((c2_x + 24, c_y + 145), "Чистая прибыль в дуэлях", font=get_font("default", 16), fill=TEXT_MUTED)
        draw.text((c2_x + 24, c_y + 180), "Учитывает все победы и ставки", font=get_font("default", 14), fill=TEXT_MUTED)
        draw.line([(c2_x + 24, c_y + c_h - 35), (c2_x + c_w - 24, c_y + c_h - 35)], fill=RED_ACCENT, width=2)

    elif page == "lottery":
        top_h = 165
        _draw_glass_panel(overlay, r_x, r_y, r_w, top_h, radius=20)
        draw_watermark_flame(draw, (r_x + 75, r_y + top_h // 2 - 12), 45, color=WATERMARK_COLOR)
        draw.text((r_x + 160, r_y + 24), "УДАЧА В ЛОТЕРЕЕ", font=get_font("bold", 19), fill=RED_ACCENT)
        bar_x = r_x + 40
        bar_w = r_w - 80
        bar_y = r_y + top_h - 32
        draw.rounded_rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + 8)], radius=4, fill=RED_TRACK)

        c_y = r_y + top_h + 16
        c_h = r_h - top_h - 16
        c_w = (r_w - 16) // 2

        # Card 1
        c1_x = r_x
        _draw_glass_panel(overlay, c1_x, c_y, c_w, c_h, radius=18)
        draw_watermark_sun(draw, (c1_x + c_w - 55, c_y + 55), 35, color=WATERMARK_COLOR)
        draw.text((c1_x + 24, c_y + 24), "СЫГРАНО ЛОТЕРЕЙ", font=get_font("bold", 16), fill=RED_ACCENT)
        draw.line([(c1_x + 24, c_y + c_h - 35), (c1_x + c_w - 24, c_y + c_h - 35)], fill=RED_ACCENT, width=2)

        # Card 2
        c2_x = r_x + c_w + 16
        _draw_glass_panel(overlay, c2_x, c_y, c_w, c_h, radius=18)
        draw_watermark_flame(draw, (c2_x + c_w - 55, c_y + 55), 45, color=WATERMARK_COLOR)
        draw.text((c2_x + 24, c_y + 24), "ВЫИГРАННЫЙ КУШ", font=get_font("bold", 16), fill=RED_ACCENT)
        draw.text((c2_x + 24, c_y + 145), "Чистая прибыль в лотереях", font=get_font("default", 16), fill=TEXT_MUTED)
        draw.text((c2_x + 24, c_y + 180), "Сумма полученных банков", font=get_font("default", 14), fill=TEXT_MUTED)
        draw.line([(c2_x + 24, c_y + c_h - 35), (c2_x + c_w - 24, c_y + c_h - 35)], fill=RED_ACCENT, width=2)

    elif page == "streaks":
        top_h = 60
        _draw_glass_panel(overlay, r_x, r_y, r_w, top_h, radius=18)
        draw.text((r_x + 28, r_y + 18), "РЕКОРДНЫЕ СЕРИИ ПОБЕД", font=get_font("bold", 19), fill=RED_ACCENT)

        card_h = 110
        gap = 14
        c_y = r_y + top_h + 14
        titles = ["ДРАКОН ДНЯ", "ЗЛОЙ ДРАКОН", "НОЧНОЙ ДРАКОН"]
        for title in titles:
            _draw_glass_panel(overlay, r_x, c_y, r_w, card_h, radius=18)
            draw.text((r_x + 74, c_y + 26), title, font=get_font("bold", 16), fill=TEXT_WHITE)
            c_y += card_h + gap

        bot_card_h = 55
        _draw_glass_panel(overlay, r_x, c_y, r_w, bot_card_h, radius=16)

    elif page == "daily":
        top_h = 136
        _draw_glass_panel(overlay, r_x, r_y, r_w, top_h, radius=20)
        fire_icon = get_emoji_icon("fire", 46)
        if fire_icon:
            overlay.paste(fire_icon, (r_x + 22, r_y + 24), mask=fire_icon)
        draw.text((r_x + 78, r_y + 18), "СЕРИЯ МАКСИМУМОВ", font=get_font("bold", 19), fill=RED_ACCENT)

        bar_x = r_x + 24
        bar_w = r_w - 48
        bar_y = r_y + 104
        draw.rounded_rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + 8)], radius=4, fill=RED_TRACK)

        c_y = r_y + top_h + 14
        c_w = (r_w - 14) // 2
        c_h = (r_h - top_h - 28) // 2
        games_def = [
            ("КУБИК", "/roll"),
            ("БАСКЕТБОЛ", "/basket"),
            ("БОУЛИНГ", "/bowling"),
            ("ФУТБОЛ", "/football"),
        ]
        for i, (g_title, g_cmd) in enumerate(games_def):
            col = i % 2
            row = i // 2
            gx = r_x + col * (c_w + 14)
            gy = c_y + row * (c_h + 14)
            _draw_glass_panel(overlay, gx, gy, c_w, c_h, radius=18)
            draw.text((gx + 22, gy + 18), g_title, font=get_font("bold", 16), fill=RED_ACCENT)
            draw.text((gx + 22, gy + 40), g_cmd, font=get_font("bold", 14), fill=TEXT_MUTED)

    # Composite into final static RGB base image
    combined = Image.alpha_composite(base, overlay)
    return combined.convert("RGB")


def get_page_static_template(page: str, bg_path: str = "images/profile_bg.png") -> Image.Image:
    key = (page, bg_path)
    if key not in _PAGE_STATIC_TEMPLATES:
        _PAGE_STATIC_TEMPLATES[key] = _build_page_static_template(page, bg_path)
    return _PAGE_STATIC_TEMPLATES[key]


# -------------------------------------------------------------------------
# Dynamic Profile Card Renderer (Blazing Fast: ~15-20ms)
# -------------------------------------------------------------------------

def render_profile_card(
    avatar_bytes: bytes | None,
    user_data: dict,
    bg_path: str = "images/profile_bg.png",
    page: str = "wins",
) -> io.BytesIO:
    """
    Renders a spacious, high-contrast profile card.
    Pre-baked static template is copied instantly (1ms), and only dynamic
    user data and stats are stamped on top.
    """
    # 1. Fetch pre-baked static template
    canvas = get_page_static_template(page, bg_path).copy()
    draw = ImageDraw.Draw(canvas)

    # Fonts
    font_name = get_font("bold", 26)
    font_points_num = get_font("bold", 32)
    font_body = get_font("default", 16)
    font_sub = get_font("default", 14)
    font_bold_sub = get_font("bold", 14)
    font_huge_num = get_font("bold", 54)
    font_large_num = get_font("bold", 36)
    font_stat_num = get_font("bold", 38)

    # 2. Left Panel Dynamic Data
    user_id = user_data.get("user_id", 0)
    display_name = user_data.get("display_name", "Игрок")
    username = user_data.get("username", "")
    points = user_data.get("points", 0)

    av_size = 145
    av_x = lp_x + (lp_w - av_size) // 2
    av_y = lp_y + 35

    # Avatar
    pasted_av = False
    if avatar_bytes:
        processed_av = get_processed_avatar(avatar_bytes, av_size)
        if processed_av:
            canvas.paste(processed_av, (av_x, av_y), processed_av)
            pasted_av = True

    if not pasted_av:
        crown_ico = get_emoji_icon("crown", 68)
        if crown_ico:
            canvas.paste(crown_ico, (av_x + (av_size - 68) // 2, av_y + (av_size - 68) // 2), mask=crown_ico)

    # Clean Name & Handle
    clean_name = display_name.strip()
    clean_user = username.strip()
    if clean_user and not clean_user.startswith("@"):
        clean_user = f"@{clean_user}"
    if clean_name.startswith("@"):
        clean_name = clean_name[1:]

    show_handle = clean_user if clean_user.lstrip("@").lower() != clean_name.lower() else ""

    # Dynamic pixel-width truncation to prevent text overflow (lp_w = 275)
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
        ub = draw.textbbox((0, 0), handle_display, font=get_font("default", 15))
        if (ub[2] - ub[0]) > max_text_w:
            for i in range(len(show_handle) - 1, 0, -1):
                cand = show_handle[:i] + "…"
                cb = draw.textbbox((0, 0), cand, font=get_font("default", 15))
                if (cb[2] - cb[0]) <= max_text_w:
                    handle_display = cand
                    break
            else:
                handle_display = show_handle[:10] + "…"
        ub = draw.textbbox((0, 0), handle_display, font=get_font("default", 15))
        uw = ub[2] - ub[0]
        draw.text((lp_x + (lp_w - uw) // 2, curr_y), handle_display, font=get_font("default", 15), fill=TEXT_MUTED)
        curr_y += 24

    id_str = f"ID: {user_id}"
    ib = draw.textbbox((0, 0), id_str, font=font_sub)
    iw = ib[2] - ib[0]
    draw.text((lp_x + (lp_w - iw) // 2, curr_y), id_str, font=font_sub, fill=(120, 132, 148, 220))

    # Points value
    sub_h = 88
    sub_y = lp_y + lp_h - sub_h - 18
    pts_str = f"{points:,}".replace(",", " ")
    draw.text((lp_x + 82, sub_y + 40), pts_str, font=font_points_num, fill=TEXT_WHITE)

    # 3. Right Panel Dynamic Content
    if page == "wins":
        wins_day = user_data.get("wins_day", 0)
        wins_evil = user_data.get("wins_evil", 0)
        wins_sleepy = user_data.get("wins_sleepy", 0)
        total_wins = wins_day + wins_evil + wins_sleepy

        tot_text = f"{total_wins} {_plural_wins(total_wins)}"
        draw.text((r_x + 98, r_y + 54), tot_text, font=font_huge_num, fill=TEXT_WHITE)

        # Breakdown on top right
        breakdown_items = [
            ("День: ", str(wins_day), "sun", r_y + 28),
            ("Злой: ", str(wins_evil), "evil", r_y + 54),
            ("Ночь: ", str(wins_sleepy), "sleepy", r_y + 80),
        ]
        for label, val_s, ico_name, item_y in breakdown_items:
            full_txt = label + val_s
            draw.text((r_x + r_w - 180, item_y), full_txt, font=font_body, fill=TEXT_WHITE)
            tb = draw.textbbox((0, 0), full_txt, font=font_body)
            tw = tb[2] - tb[0]
            ico = get_emoji_icon(ico_name, 16)
            if ico:
                canvas.paste(ico, (r_x + r_w - 180 + tw + 6, item_y + 1), mask=ico)

        # Dragon cards counts
        card_h = 110
        gap = 14
        c_y = r_y + 130 + 16
        dragons_counts = [
            f"{wins_day} {_plural_wins(wins_day)}",
            f"{wins_evil} {_plural_wins(wins_evil)}",
            f"{wins_sleepy} {_plural_wins(wins_sleepy)}",
        ]
        for count_text in dragons_counts:
            vb = draw.textbbox((0, 0), count_text, font=font_large_num)
            vw = vb[2] - vb[0]
            draw.text((r_x + r_w - 28 - vw, c_y + 36), count_text, font=font_large_num, fill=TEXT_WHITE)
            c_y += card_h + gap

    elif page == "bets":
        bets_played = user_data.get("bets_played", 0)
        bets_won = user_data.get("bets_won", 0)
        winrate = round((bets_won / bets_played * 100)) if bets_played > 0 else 0
        open_bets = user_data.get("open_bets", 0)

        win_str = f"{winrate}%"
        draw.text((r_x + 160, r_y + 50), win_str, font=font_huge_num, fill=TEXT_WHITE)
        draw.text((r_x + r_w - 240, r_y + 32), f"Выиграно: {bets_won} из {bets_played}", font=font_body, fill=TEXT_WHITE)
        draw.text((r_x + r_w - 240, r_y + 60), f"Открыто сегодня: {open_bets}", font=font_body, fill=TEXT_MUTED)

        # Progress bar fill
        bar_x = r_x + 40
        bar_w = r_w - 80
        bar_y = r_y + 165 - 32
        fill_w = int(bar_w * (winrate / 100.0))
        if fill_w > 0:
            draw.rounded_rectangle([(bar_x, bar_y), (bar_x + fill_w, bar_y + 8)], radius=4, fill=RED_ACCENT)

        top_h = 165
        c_y = r_y + top_h + 16
        c_h = r_h - top_h - 16
        c_w = (r_w - 16) // 2

        # Card 1
        c1_x = r_x
        draw.text((c1_x + 24, c_y + 60), str(bets_played), font=font_huge_num, fill=TEXT_WHITE)
        draw.text((c1_x + 24, c_y + 145), f"Успешных ставок: {bets_won}", font=font_body, fill=TEXT_MUTED)
        draw.text((c1_x + 24, c_y + 180), f"Проигранных: {max(0, bets_played - bets_won)}", font=font_body, fill=TEXT_MUTED)

        # Card 2
        c2_x = r_x + c_w + 16
        draw.text((c2_x + 24, c_y + 60), str(open_bets), font=font_huge_num, fill=TEXT_WHITE)

    elif page == "duels":
        duels_played = user_data.get("duels_played", 0)
        duels_won = user_data.get("duels_won", 0)
        duels_points_won = user_data.get("duels_points_won", user_data.get("duel_points_won", 0))
        duel_winrate = round((duels_won / duels_played * 100)) if duels_played > 0 else 0

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
            canvas.paste(c_ico, (r_x + r_w - 240 + nw + 6, r_y + 61), mask=c_ico)

        # Progress bar fill
        bar_x = r_x + 40
        bar_w = r_w - 80
        bar_y = r_y + 165 - 32
        fill_w = int(bar_w * (duel_winrate / 100.0))
        if fill_w > 0:
            draw.rounded_rectangle([(bar_x, bar_y), (bar_x + fill_w, bar_y + 8)], radius=4, fill=RED_ACCENT)

        top_h = 165
        c_y = r_y + top_h + 16
        c_h = r_h - top_h - 16
        c_w = (r_w - 16) // 2

        # Card 1
        c1_x = r_x
        draw.text((c1_x + 24, c_y + 60), str(duels_played), font=font_huge_num, fill=TEXT_WHITE)
        draw.text((c1_x + 24, c_y + 145), f"Выиграно дуэлей: {duels_won}", font=font_body, fill=TEXT_MUTED)
        draw.text((c1_x + 24, c_y + 180), f"Поражений / ничьих: {max(0, duels_played - duels_won)}", font=font_body, fill=TEXT_MUTED)

        # Card 2
        c2_x = r_x + c_w + 16
        pts_won_str = f"{duels_points_won:,}".replace(",", " ")
        draw.text((c2_x + 24, c_y + 60), pts_won_str, font=font_huge_num, fill=TEXT_WHITE)

    elif page == "lottery":
        lottery_played = user_data.get("lottery_played", 0)
        lottery_won = user_data.get("lottery_won", 0)
        lottery_points_won = user_data.get("lottery_points_won", 0)
        lottery_winrate = round((lottery_won / lottery_played * 100)) if lottery_played > 0 else 0

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
            canvas.paste(c_ico, (r_x + r_w - 240 + kw + 6, r_y + 61), mask=c_ico)

        # Progress bar fill
        bar_x = r_x + 40
        bar_w = r_w - 80
        bar_y = r_y + 165 - 32
        fill_w = int(bar_w * (lottery_winrate / 100.0))
        if fill_w > 0:
            draw.rounded_rectangle([(bar_x, bar_y), (bar_x + fill_w, bar_y + 8)], radius=4, fill=RED_ACCENT)

        top_h = 165
        c_y = r_y + top_h + 16
        c_h = r_h - top_h - 16
        c_w = (r_w - 16) // 2

        # Card 1
        c1_x = r_x
        draw.text((c1_x + 24, c_y + 60), str(lottery_played), font=font_huge_num, fill=TEXT_WHITE)
        draw.text((c1_x + 24, c_y + 145), f"Выиграно джекпотов: {lottery_won}", font=font_body, fill=TEXT_MUTED)
        draw.text((c1_x + 24, c_y + 180), f"Без выигрыша: {max(0, lottery_played - lottery_won)}", font=font_body, fill=TEXT_MUTED)

        # Card 2
        c2_x = r_x + c_w + 16
        l_pts_str = f"{lottery_points_won:,}".replace(",", " ")
        draw.text((c2_x + 24, c_y + 60), l_pts_str, font=font_huge_num, fill=TEXT_WHITE)

    elif page == "streaks":
        _, day_dates_str = format_streak_dates(
            user_data.get("max_streak_day", 0),
            user_data.get("max_streak_day_start"),
            user_data.get("max_streak_day_end"),
        )
        _, evil_dates_str = format_streak_dates(
            user_data.get("max_streak_evil", 0),
            user_data.get("max_streak_evil_start"),
            user_data.get("max_streak_evil_end"),
        )
        _, sleepy_dates_str = format_streak_dates(
            user_data.get("max_streak_sleepy", 0),
            user_data.get("max_streak_sleepy_start"),
            user_data.get("max_streak_sleepy_end"),
        )

        streaks = [
            (user_data.get("max_streak_day", 0), day_dates_str),
            (user_data.get("max_streak_evil", 0), evil_dates_str),
            (user_data.get("max_streak_sleepy", 0), sleepy_dates_str),
        ]

        card_h = 110
        gap = 14
        top_h = 60
        c_y = r_y + top_h + 14

        for count, dates_txt in streaks:
            has_streak = count > 0
            cb_size = 32
            cb_x = r_x + 24
            cb_cy = c_y + card_h // 2 - cb_size // 2

            if has_streak:
                draw.rounded_rectangle([(cb_x, cb_cy), (cb_x + cb_size, cb_cy + cb_size)], radius=8, fill=RED_ACCENT)
                draw_checkmark(draw, (cb_x + cb_size // 2, cb_cy + cb_size // 2), 8, TEXT_WHITE, width=3)
            else:
                draw.rounded_rectangle([(cb_x, cb_cy), (cb_x + cb_size, cb_cy + cb_size)], radius=8, fill=(28, 33, 44, 200), outline=CARD_BORDER, width=2)

            draw.text((r_x + 74, c_y + 58), dates_txt, font=font_body, fill=TEXT_MUTED)

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

        max_overall = max(
            user_data.get("max_streak_day", 0),
            user_data.get("max_streak_evil", 0),
            user_data.get("max_streak_sleepy", 0),
        )
        active_count = sum(1 for count, _ in streaks if count > 0)
        draw.text((r_x + 28, c_y + 18), f"Рекорд серий: {max_overall} дн.", font=get_font("bold", 16), fill=TEXT_WHITE)
        draw.text((r_x + r_w - 180, c_y + 18), f"Категорий: {active_count} из 3", font=font_body, fill=RED_ACCENT)

    elif page == "daily":
        daily_games = user_data.get("daily_games", {})
        cur_streak = user_data.get("current_streak_daily_max", 0)
        max_streak = user_data.get("max_streak_daily_max", 0)
        played_count = len(daily_games)

        streak_str = f"{cur_streak} дн."
        draw.text((r_x + 78, r_y + 44), streak_str, font=font_stat_num, fill=TEXT_WHITE)

        sb = draw.textbbox((0, 0), streak_str, font=font_stat_num)
        sw = sb[2] - sb[0]
        draw.text((r_x + 78 + sw + 12, r_y + 58), "подряд без сброса", font=font_sub, fill=TEXT_MUTED)

        rec_text = f"Рекорд: {max_streak} дн. подряд"
        chances_text = f"Шансы: {played_count} из 4"
        rb = draw.textbbox((0, 0), rec_text, font=font_body)
        rw = rb[2] - rb[0]
        draw.text((r_x + r_w - 24 - rw, r_y + 20), rec_text, font=font_body, fill=TEXT_WHITE)

        cb = draw.textbbox((0, 0), chances_text, font=font_body)
        cw = cb[2] - cb[0]
        draw.text((r_x + r_w - 24 - cw, r_y + 48), chances_text, font=font_body, fill=TEXT_MUTED)

        # Progress bar fill
        bar_x = r_x + 24
        bar_w = r_w - 48
        bar_y = r_y + 104
        fill_w = int(bar_w * (min(4, played_count) / 4.0))
        if fill_w > 0:
            draw.rounded_rectangle([(bar_x, bar_y), (bar_x + fill_w, bar_y + 8)], radius=4, fill=RED_ACCENT)

        top_h = 136
        c_y = r_y + top_h + 14
        c_w = (r_w - 14) // 2
        c_h = (r_h - top_h - 28) // 2

        games_def = [
            ("dice", 6),
            ("basket", 5),
            ("bowling", 6),
            ("football", 5),
        ]

        for i, (g_key, max_val) in enumerate(games_def):
            col = i % 2
            row = i // 2
            gx = r_x + col * (c_w + 14)
            gy = c_y + row * (c_h + 14)

            g_info = daily_games.get(g_key)
            is_played = g_info is not None

            if is_played:
                val = g_info.get("value", 0)
                pts = g_info.get("points", 0)
                is_max = g_info.get("is_max", False)
                pts_str = f"+{pts}" if pts > 0 else str(pts)

                badge_text = "ДЖЕКПОТ" if is_max else "СЫГРАНО"
                bb = draw.textbbox((0, 0), badge_text, font=font_bold_sub)
                bw = bb[2] - bb[0] + 16
                bh = 22
                bx = gx + c_w - bw - 18
                by = gy + 18
                b_color = (235, 75, 90, 255) if is_max else (52, 211, 153, 255)
                draw.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=6, outline=b_color, width=1)
                draw.text((bx + 8, by + 3), badge_text, font=font_bold_sub, fill=b_color)

                draw.text((gx + 22, gy + 68), f"{val} / {max_val}", font=font_large_num, fill=TEXT_WHITE)
                draw.text((gx + 22, gy + 118), f"Очки: {pts_str}", font=font_body, fill=RED_ACCENT if is_max else TEXT_MUTED)
                draw.line([(gx + 22, gy + c_h - 18), (gx + c_w - 22, gy + c_h - 18)], fill=b_color, width=2)
            else:
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

    # 4. Save to BytesIO using fast lossless PNG (compress_level=1)
    output = io.BytesIO()
    canvas.save(output, format="PNG", compress_level=1)
    output.seek(0)
    return output
