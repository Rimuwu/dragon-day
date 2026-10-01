import io
import math
import os
from PIL import Image, ImageDraw, ImageFont

_EMOJI_CACHE: dict[tuple[str, int], Image.Image] = {}


def get_emoji_icon(name: str, size: int = 20) -> Image.Image | None:
    cache_key = (name, size)
    if cache_key in _EMOJI_CACHE:
        return _EMOJI_CACHE[cache_key]
    path = os.path.join("assets", "emojis", f"{name}.png")
    if not os.path.exists(path):
        return None
    try:
        img = Image.open(path).convert("RGBA")
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        _EMOJI_CACHE[cache_key] = resized
        return resized
    except Exception:
        return None



def create_circle_mask(size: int) -> Image.Image:
    scale = 4
    dim = size * scale
    mask = Image.new("L", (dim, dim), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([(0, 0), (dim - 1, dim - 1)], fill=255)
    return mask.resize((size, size), Image.Resampling.LANCZOS)


def render_leaderboard_podium(
    top_players: list[dict],
    kind: str = "points",
) -> io.BytesIO:
    """
    Renders a visual podium image with circular avatars of the top 3 players:
    - 1st Place (Center, Gold, tallest)
    - 2nd Place (Left, Silver, medium)
    - 3rd Place (Right, Bronze, low)
    """
    W, H = 960, 440
    canvas = Image.new("RGBA", (W, H), (14, 16, 20, 255))
    draw = ImageDraw.Draw(canvas)

    # Fonts
    try:
        font_title = ImageFont.truetype("fonts/bold.ttf", 24)
        font_sub = ImageFont.truetype("fonts/default.ttf", 13)
        font_name_1 = ImageFont.truetype("fonts/bold.ttf", 17)
        font_name_23 = ImageFont.truetype("fonts/bold.ttf", 15)
        font_rank = ImageFont.truetype("fonts/bold.ttf", 26)
        font_val_1 = ImageFont.truetype("fonts/bold.ttf", 16)
        font_val_23 = ImageFont.truetype("fonts/bold.ttf", 14)
        font_badge = ImageFont.truetype("fonts/bold.ttf", 14)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = font_title
        font_name_1 = font_title
        font_name_23 = font_title
        font_rank = font_title
        font_val_1 = font_title
        font_val_23 = font_title
        font_badge = font_title

    # Outer container with rounded corners and sleek border
    draw.rounded_rectangle(
        [(10, 10), (W - 10, H - 10)],
        radius=24,
        fill=(18, 20, 26, 255),
        outline=(38, 42, 54, 255),
        width=2,
    )

    # Header section
    category_titles = {
        "points": ("РЕЙТИНГ ЛИДЕРОВ", "Топ игроков по накопленным очкам"),
        "day": ("ЗАЛ СЛАВЫ: ДРАКОНЫ ДНЯ", "Топ игроков по победам в Драконе Дня"),
        "evil": ("ЗАЛ СЛАВЫ: ЗЛЫЕ ДРАКОНЫ", "Топ игроков по победам в Злом Драконе"),
        "sleepy": ("ЗАЛ СЛАВЫ: СОННЫЕ ДРАКОНЫ", "Топ игроков по победам в Сонном Драконе"),
    }
    title_text, subtitle_text = category_titles.get(kind, ("РЕЙТИНГ ЛИДЕРОВ", "Топ игроков"))

    # Title centered
    tb = draw.textbbox((0, 0), title_text, font=font_title)
    tw = tb[2] - tb[0]
    draw.text(((W - tw) // 2, 24), title_text, font=font_title, fill=(245, 248, 252, 255))

    stb = draw.textbbox((0, 0), subtitle_text, font=font_sub)
    stw = stb[2] - stb[0]
    draw.text(((W - stw) // 2, 56), subtitle_text, font=font_sub, fill=(135, 145, 160, 255))

    # Divider
    draw.line([(80, 80), (W - 80, 80)], fill=(32, 36, 46, 255), width=1)

    # Podium Configuration
    # 1st place in center (index 0)
    # 2nd place on left (index 1)
    # 3rd place on right (index 2)
    podium_slots = [
        {
            "rank": 1,
            "color_name": "gold",
            "border_col": (255, 205, 50, 255),
            "pedestal_bg": (38, 32, 20, 255),
            "pedestal_border": (210, 165, 35, 255),
            "cx": 480,
            "av_size": 104,
            "av_y": 105,
            "pedestal_y": 270,
            "pedestal_h": 140,
            "font_name": font_name_1,
            "font_val": font_val_1,
        },
        {
            "rank": 2,
            "color_name": "silver",
            "border_col": (195, 205, 220, 255),
            "pedestal_bg": (28, 32, 40, 255),
            "pedestal_border": (155, 165, 185, 255),
            "cx": 215,
            "av_size": 88,
            "av_y": 140,
            "pedestal_y": 305,
            "pedestal_h": 105,
            "font_name": font_name_23,
            "font_val": font_val_23,
        },
        {
            "rank": 3,
            "color_name": "bronze",
            "border_col": (205, 130, 65, 255),
            "pedestal_bg": (36, 26, 22, 255),
            "pedestal_border": (175, 100, 45, 255),
            "cx": 745,
            "av_size": 88,
            "av_y": 160,
            "pedestal_y": 325,
            "pedestal_h": 85,
            "font_name": font_name_23,
            "font_val": font_val_23,
        },
    ]

    for slot in podium_slots:
        r = slot["rank"]
        player = top_players[r - 1] if len(top_players) >= r else None
        cx = slot["cx"]
        av_size = slot["av_size"]
        av_y = slot["av_y"]
        ped_y = slot["pedestal_y"]
        ped_h = slot["pedestal_h"]
        border_col = slot["border_col"]
        ped_bg = slot["pedestal_bg"]
        ped_border = slot["pedestal_border"]

        # Pedestal block
        ped_w = 180
        ped_x = cx - ped_w // 2
        draw.rounded_rectangle(
            [(ped_x, ped_y), (ped_x + ped_w, ped_y + ped_h)],
            radius=14,
            fill=ped_bg,
            outline=ped_border,
            width=2,
        )

        # Rank number inside pedestal
        rank_str = f"#{r}"
        rb = draw.textbbox((0, 0), rank_str, font=font_rank)
        rw = rb[2] - rb[0]
        draw.text((cx - rw // 2, ped_y + 14), rank_str, font=font_rank, fill=border_col)

        # Value inside pedestal (points or wins) with matching emoji icon
        emoji_map = {
            "points": "coin",
            "day": "sun",
            "evil": "evil",
            "sleepy": "sleepy",
        }
        emoji_name = emoji_map.get(kind, "coin")

        if player:
            if kind == "points":
                val = player.get("points", player.get("value", 0))
            elif kind == "day":
                val = player.get("wins_day", player.get("value", 0))
            elif kind == "evil":
                val = player.get("wins_evil", player.get("value", 0))
            else:
                val = player.get("wins_sleepy", player.get("value", 0))
            val_str = f"{val:,}".replace(",", " ")
        else:
            val_str = "—"

        vb = draw.textbbox((0, 0), val_str, font=slot["font_val"])
        vw = vb[2] - vb[0]
        vh = vb[3] - vb[1]

        icon_size = 20 if r == 1 else 17
        icon = get_emoji_icon(emoji_name, icon_size) if player else None

        if icon:
            gap = 6
            total_w = vw + gap + icon_size
            start_x = cx - total_w // 2
            text_y = ped_y + 54
            draw.text((start_x, text_y), val_str, font=slot["font_val"], fill=(245, 248, 252, 255))
            icon_y = text_y + (vh - icon_size) // 2 + 1
            canvas.paste(icon, (start_x + vw + gap, icon_y), mask=icon)
        else:
            draw.text((cx - vw // 2, ped_y + 54), val_str, font=slot["font_val"], fill=(245, 248, 252, 255))

        # Crown / Medal indicator above avatar
        if r == 1:
            # Gold crown above #1
            crown_pts = [
                (cx - 18, av_y - 12),
                (cx - 24, av_y - 28),
                (cx - 10, av_y - 20),
                (cx, av_y - 32),
                (cx + 10, av_y - 20),
                (cx + 24, av_y - 28),
                (cx + 18, av_y - 12),
            ]
            draw.polygon(crown_pts, fill=(255, 215, 0, 255), outline=(210, 165, 30, 255), width=1)
            draw.line([(cx - 18, av_y - 10), (cx + 18, av_y - 10)], fill=(255, 215, 0, 255), width=2)
        elif r == 2:
            # Silver star badge
            draw.ellipse([(cx - 12, av_y - 26), (cx + 12, av_y - 2)], fill=(195, 205, 220, 255), outline=(155, 165, 185, 255), width=1)
            draw.text((cx - 5, av_y - 23), "2", font=slot["font_val"], fill=(20, 24, 30, 255))
        elif r == 3:
            # Bronze star badge
            draw.ellipse([(cx - 12, av_y - 26), (cx + 12, av_y - 2)], fill=(205, 130, 65, 255), outline=(175, 100, 45, 255), width=1)
            draw.text((cx - 5, av_y - 23), "3", font=slot["font_val"], fill=(20, 24, 30, 255))

        # Avatar circle
        av_x = cx - av_size // 2
        draw.ellipse(
            [(av_x - 4, av_y - 4), (av_x + av_size + 4, av_y + av_size + 4)],
            outline=border_col,
            width=3,
        )
        draw.ellipse(
            [(av_x, av_y), (av_x + av_size, av_y + av_size)],
            fill=(30, 34, 44, 255),
        )

        av_bytes = player.get("avatar_bytes") if player else None
        if av_bytes:
            try:
                raw_av = Image.open(io.BytesIO(av_bytes)).convert("RGBA")
                scaled_av = raw_av.resize((av_size, av_size), Image.Resampling.LANCZOS)
                mask = create_circle_mask(av_size)
                canvas.paste(scaled_av, (av_x, av_y), mask)
            except Exception:
                av_bytes = None

        if not av_bytes:
            d_name = (player.get("display_name") or player.get("name") or "") if player else ""
            initial = (d_name or "?")[:1].upper() if player else "—"
            ib = draw.textbbox((0, 0), initial, font=font_title)
            iw = ib[2] - ib[0]
            ih = ib[3] - ib[1]
            draw.text((cx - iw // 2, av_y + (av_size - ih) // 2 - 2), initial, font=font_title, fill=border_col)

        # Player Name (positioned between avatar and pedestal)
        if player:
            name = player.get("display_name") or player.get("name") or "Игрок"
            name = name[:12] + "…" if len(name) > 13 else name
        else:
            name = "Свободно"

        nb = draw.textbbox((0, 0), name, font=slot["font_name"])
        nw = nb[2] - nb[0]
        draw.text((cx - nw // 2, ped_y - 28), name, font=slot["font_name"], fill=(245, 248, 252, 255))

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
