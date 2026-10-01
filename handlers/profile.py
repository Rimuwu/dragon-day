import io
import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputRichBlockPhoto,
    InputRichBlockTable,
    InputRichMessage,
    Message,
    RichBlockTableCell,
    RichText,
    RichTextBold,
)

from utils.card_cache import (
    get_cached_avatar,
    get_cached_card,
    set_cached_avatar,
    set_cached_card,
    update_cached_file_id,
)
from utils.context import AppContext
from utils.custom_emojis import fmt_emoji, get_emoji_id
from utils.guards import ensure_group_message, ensure_participant, ensure_supported_group
from utils.helpers import format_user_name
from utils.profile_card import render_profile_card
from utils.time_utils import today_str

logger = logging.getLogger(__name__)


def get_profile_keyboard(user_id: int, current_page: str = "wins") -> InlineKeyboardMarkup:
    row1 = [
        ("wins", "Победы", "crown", "👑"),
        ("bets", "Ставки", "dice", "🎲"),
        ("streaks", "Серии", "fire", "🔥"),
    ]
    row2 = [
        ("duels", "Дуэли", "dice", "⚔️"),
        ("lottery", "Лотерея", "coin", "🎟️"),
        ("daily", "Шансы", "dice", "🎯"),
    ]
    keyboard = []
    for r in (row1, row2):
        btns = []
        for page_key, label, emoji_key, fallback_emoji in r:
            e_id = get_emoji_id(emoji_key)
            display_label = label if e_id else f"{fallback_emoji} {label}"
            is_active = (page_key == current_page)
            btns.append(
                InlineKeyboardButton(
                    text=display_label,
                    icon_custom_emoji_id=e_id,
                    callback_data=f"prof:{user_id}:{page_key}",
                    style="primary" if is_active else None,
                )
            )
        keyboard.append(btns)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _format_streak(count: int, start_date: str | None, end_date: str | None) -> str:
    if not count or count <= 0:
        return "—"
    if count % 10 == 1 and count % 100 != 11:
        word = "победа"
    elif 2 <= count % 10 <= 4 and not (12 <= count % 100 <= 14):
        word = "победы"
    else:
        word = "побед"

    def _fmt(d: str) -> str:
        try:
            parts = d.split("-")
            if len(parts) == 3:
                return f"{parts[2]}.{parts[1]}.{parts[0]}"
        except Exception:
            pass
        return d

    if not start_date and not end_date:
        return f"{count} {word}"
    if start_date and (not end_date or start_date == end_date):
        return f"{count} {word} ({_fmt(start_date)})"
    if start_date and end_date:
        return f"{count} {word} (с {_fmt(start_date)} по {_fmt(end_date)})"
    return f"{count} {word}"


def build_profile_table_block(user_data: dict) -> InputRichBlockTable:
    display_name = user_data["display_name"]
    user_id = user_data["user_id"]
    points = user_data["points"]
    wins_day = user_data["wins_day"]
    wins_evil = user_data["wins_evil"]
    wins_sleepy = user_data["wins_sleepy"]
    total_wins = wins_day + wins_evil + wins_sleepy
    bets_played = user_data["bets_played"]
    bets_won = user_data["bets_won"]
    winrate = round((bets_won / bets_played * 100)) if bets_played > 0 else 0
    open_bets = user_data["open_bets"]

    day_streak = _format_streak(
        user_data.get("max_streak_day", 0),
        user_data.get("max_streak_day_start"),
        user_data.get("max_streak_day_end"),
    )
    evil_streak = _format_streak(
        user_data.get("max_streak_evil", 0),
        user_data.get("max_streak_evil_start"),
        user_data.get("max_streak_evil_end"),
    )
    sleepy_streak = _format_streak(
        user_data.get("max_streak_sleepy", 0),
        user_data.get("max_streak_sleepy_start"),
        user_data.get("max_streak_sleepy_end"),
    )

    rows = [
        [
            RichBlockTableCell(
                text=RichTextBold(text=f"Профиль: {display_name} (ID: {user_id})"),
                align="left",
                valign="middle",
                colspan=3,
                is_header=True,
            )
        ],
        [
            RichBlockTableCell(text=get_rich_emoji("coin", "🪙"), align="center", valign="middle"),
            RichBlockTableCell(text=RichTextBold(text="Очки"), align="left", valign="middle"),
            RichBlockTableCell(text=RichText(text=f"{points:,}".replace(",", " ")), align="right", valign="middle"),
        ],
        [
            RichBlockTableCell(text=get_rich_emoji("sun", "☀️"), align="center", valign="middle"),
            RichBlockTableCell(text=RichTextBold(text="Дракон Дня"), align="left", valign="middle"),
            RichBlockTableCell(text=RichText(text=f"{wins_day}"), align="right", valign="middle"),
        ],
        [
            RichBlockTableCell(text=get_rich_emoji("evil", "😈"), align="center", valign="middle"),
            RichBlockTableCell(text=RichTextBold(text="Злой Дракон"), align="left", valign="middle"),
            RichBlockTableCell(text=RichText(text=f"{wins_evil}"), align="right", valign="middle"),
        ],
        [
            RichBlockTableCell(text=get_rich_emoji("sleepy", "🌙"), align="center", valign="middle"),
            RichBlockTableCell(text=RichTextBold(text="Сонный Дракон"), align="left", valign="middle"),
            RichBlockTableCell(text=RichText(text=f"{wins_sleepy}"), align="right", valign="middle"),
        ],
        [
            RichBlockTableCell(text=get_rich_emoji("crown", "👑"), align="center", valign="middle"),
            RichBlockTableCell(text=RichTextBold(text="Всего побед"), align="left", valign="middle"),
            RichBlockTableCell(text=RichText(text=f"{total_wins}"), align="right", valign="middle"),
        ],
        [
            RichBlockTableCell(text=get_rich_emoji("dice", "🎲"), align="center", valign="middle"),
            RichBlockTableCell(text=RichTextBold(text="Ставки"), align="left", valign="middle"),
            RichBlockTableCell(text=RichText(text=f"{bets_won} из {bets_played} ({winrate}%)"), align="right", valign="middle"),
        ],
        [
            RichBlockTableCell(text=RichText(text="⏳"), align="center", valign="middle"),
            RichBlockTableCell(text=RichTextBold(text="Открыто ставок"), align="left", valign="middle"),
            RichBlockTableCell(text=RichText(text=f"{open_bets}"), align="right", valign="middle"),
        ],
        [
            RichBlockTableCell(text=get_rich_emoji("fire", "🔥"), align="center", valign="middle"),
            RichBlockTableCell(text=RichTextBold(text="Серия Дня"), align="left", valign="middle"),
            RichBlockTableCell(text=RichText(text=day_streak), align="right", valign="middle"),
        ],
        [
            RichBlockTableCell(text=get_rich_emoji("fire", "🔥"), align="center", valign="middle"),
            RichBlockTableCell(text=RichTextBold(text="Серия Злого"), align="left", valign="middle"),
            RichBlockTableCell(text=RichText(text=evil_streak), align="right", valign="middle"),
        ],
        [
            RichBlockTableCell(text=get_rich_emoji("fire", "🔥"), align="center", valign="middle"),
            RichBlockTableCell(text=RichTextBold(text="Серия Сонного"), align="left", valign="middle"),
            RichBlockTableCell(text=RichText(text=sleepy_streak), align="right", valign="middle"),
        ],
    ]
    return InputRichBlockTable(cells=rows, is_bordered=True, is_striped=True)


def build_profile_caption(user_data: dict, current_page: str = "wins") -> str:
    raw_name = user_data["display_name"]
    display_name = raw_name if len(raw_name) <= 28 else raw_name[:27] + "…"
    user_id = user_data["user_id"]
    points = user_data["points"]
    wins_day = user_data["wins_day"]
    wins_evil = user_data["wins_evil"]
    wins_sleepy = user_data["wins_sleepy"]
    total_wins = wins_day + wins_evil + wins_sleepy
    bets_played = user_data["bets_played"]
    bets_won = user_data["bets_won"]
    winrate = round((bets_won / bets_played * 100)) if bets_played > 0 else 0
    open_bets = user_data["open_bets"]

    day_streak = _format_streak(
        user_data.get("max_streak_day", 0),
        user_data.get("max_streak_day_start"),
        user_data.get("max_streak_day_end"),
    )
    evil_streak = _format_streak(
        user_data.get("max_streak_evil", 0),
        user_data.get("max_streak_evil_start"),
        user_data.get("max_streak_evil_end"),
    )
    sleepy_streak = _format_streak(
        user_data.get("max_streak_sleepy", 0),
        user_data.get("max_streak_sleepy_start"),
        user_data.get("max_streak_sleepy_end"),
    )

    duels_played = user_data.get("duels_played", 0)
    duels_won = user_data.get("duels_won", 0)
    duels_points_won = user_data.get("duels_points_won", 0)
    duel_winrate = round((duels_won / duels_played * 100)) if duels_played > 0 else 0
    duels_pts_str = f"+{duels_points_won:,}" if duels_points_won >= 0 else f"{duels_points_won:,}"

    lottery_played = user_data.get("lottery_played", 0)
    lottery_won = user_data.get("lottery_won", 0)
    lottery_points_won = user_data.get("lottery_points_won", 0)
    lottery_pts_str = f"+{lottery_points_won:,}" if lottery_points_won >= 0 else f"{lottery_points_won:,}"

    coin_e = fmt_emoji("coin", "🪙")
    sun_e = fmt_emoji("sun", "☀️")
    evil_e = fmt_emoji("evil", "😈")
    sleepy_e = fmt_emoji("sleepy", "🌙")
    crown_e = fmt_emoji("crown", "👑")
    dice_e = fmt_emoji("dice", "🎲")
    fire_e = fmt_emoji("fire", "🔥")

    if current_page == "daily":
        daily_games = user_data.get("daily_games", {})
        cur_streak = user_data.get("current_streak_daily_max", 0)
        max_streak = user_data.get("max_streak_daily_max", 0)

        def _game_line(emoji: str, name: str, cmd: str, g_key: str, max_val: int) -> str:
            info = daily_games.get(g_key)
            if info:
                val = info.get("value", 0)
                pts = info.get("points", 0)
                pts_sign = f"+{pts}" if pts > 0 else str(pts)
                star = " ⭐ МАКСИМУМ!" if info.get("is_max") else ""
                return f"{emoji} <b>{name}</b> (<code>{cmd}</code>): ✅ <b>{val}/{max_val}</b> ({pts_sign} очков){star}"
            else:
                return f"{emoji} <b>{name}</b> (<code>{cmd}</code>): 🟢 <b>Доступно</b>"

        dice_line = _game_line("🎲", "Кубик", "/roll", "dice", 6)
        basket_line = _game_line("🏀", "Баскетбол", "/basket", "basket", 5)
        bowling_line = _game_line("🎳", "Боулинг", "/bowling", "bowling", 6)
        football_line = _game_line("⚽", "Футбол", "/football", "football", 5)

        return (
            f"👤 <b>Ежедневные шансы:</b> {display_name} (<code>ID: {user_id}</code>)\n"
            f"────────────────────\n"
            f"{coin_e} <b>Очки:</b> {points:,}\n"
            f"────────────────────\n"
            f"{dice_line}\n"
            f"{basket_line}\n"
            f"{bowling_line}\n"
            f"{football_line}\n"
            f"────────────────────\n"
            f"{fire_e} <b>Серия максимумов:</b> <b>{cur_streak} дн. подряд</b>\n"
            f"🏆 <b>Рекорд серии:</b> <b>{max_streak} дн. подряд</b>\n"
            f"<i>Испытывайте удачу каждый день и ставьте новые рекорды!</i>"
        ).replace(",", " ")

    return (
        f"👤 <b>Профиль игрока:</b> {display_name} (<code>ID: {user_id}</code>)\n"
        f"────────────────────\n"
        f"{coin_e} <b>Очки:</b> {points:,}\n"
        f"{sun_e} <b>Дракон Дня:</b> {wins_day}\n"
        f"{evil_e} <b>Злой Дракон:</b> {wins_evil}\n"
        f"{sleepy_e} <b>Сонный Дракон:</b> {wins_sleepy}\n"
        f"{crown_e} <b>Всего побед:</b> {total_wins}\n"
        f"────────────────────\n"
        f"{dice_e} <b>Ставки:</b> {bets_won} из {bets_played} ({winrate}%)\n"
        f"⏳ <b>Открыто сегодня:</b> {open_bets}\n"
        f"────────────────────\n"
        f"{dice_e} <b>Дуэли:</b> {duels_won} из {duels_played} ({duel_winrate}%, {duels_pts_str})\n"
        f"{coin_e} <b>Лотерея:</b> {lottery_won} из {lottery_played} ({lottery_pts_str})\n"
        f"────────────────────\n"
        f"{fire_e} <b>Серия дня:</b> {day_streak}\n"
        f"{fire_e} <b>Серия злого:</b> {evil_streak}\n"
        f"{fire_e} <b>Серия сонного:</b> {sleepy_streak}"
    ).replace(",", " ")


async def fetch_user_avatar(bot, user_id: int) -> bytes | None:
    cached = get_cached_avatar(user_id)
    if cached is not None:
        return cached[1]
    avatar_bytes = None
    try:
        user_photos = await bot.get_user_profile_photos(user_id, limit=1)
        if user_photos and user_photos.total_count > 0:
            photo_file = user_photos.photos[0][-1]
            file_info = await bot.get_file(photo_file.file_id)
            if file_info.file_path:
                buf = io.BytesIO()
                await bot.download_file(file_info.file_path, buf)
                avatar_bytes = buf.getvalue()
    except Exception as e:
        logger.debug("Failed to fetch avatar for user %s: %s", user_id, e)
    set_cached_avatar(user_id, avatar_bytes)
    return avatar_bytes


async def get_or_render_card(bot, chat_id: int, user_data: dict, bg_path: str, page: str = "wins") -> tuple[bytes, str | None]:
    user_id = user_data["user_id"]
    cached = get_cached_card(chat_id, user_id, page)
    if cached is not None:
        return cached

    avatar_bytes = await fetch_user_avatar(bot, user_id)
    card_buf = render_profile_card(avatar_bytes, user_data, bg_path=bg_path, page=page)
    card_bytes = card_buf.getvalue()
    set_cached_card(chat_id, user_id, page, card_bytes)
    return card_bytes, None


def get_router(ctx: AppContext) -> Router:
    router = Router()

    @router.message(Command("me"))
    async def cmd_me(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        if not message.from_user:
            return
        if not await ensure_participant(ctx, message):
            return

        ctx.db.upsert_user(
            message.chat.id,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        ctx.db.sync_user(
            message.chat.id,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        stats = ctx.db.get_user_stats(message.chat.id, message.from_user.id)
        if not stats:
            return

        points = stats["points"]
        wins_day = stats["wins_day"]
        wins_evil = stats["wins_evil"]
        wins_sleepy = stats["wins_sleepy"]
        bets_played = stats["bets_played"]
        bets_won = stats["bets_won"]
        open_bets = ctx.db.count_open_bets(message.chat.id, message.from_user.id, today_str(ctx.tz))

        display_name = format_user_name(
            message.from_user.id,
            message.from_user.username or stats.get("username"),
            message.from_user.first_name or stats.get("first_name"),
            message.from_user.last_name or stats.get("last_name"),
        )

        user_data = {
            "display_name": display_name,
            "username": message.from_user.username or stats.get("username") or "",
            "user_id": message.from_user.id,
            "points": points,
            "wins_day": wins_day,
            "wins_evil": wins_evil,
            "wins_sleepy": wins_sleepy,
            "bets_played": bets_played,
            "bets_won": bets_won,
            "open_bets": open_bets,
            "max_streak_day": stats.get("max_streak_day", 0),
            "max_streak_day_start": stats.get("max_streak_day_start"),
            "max_streak_day_end": stats.get("max_streak_day_end"),
            "max_streak_evil": stats.get("max_streak_evil", 0),
            "max_streak_evil_start": stats.get("max_streak_evil_start"),
            "max_streak_evil_end": stats.get("max_streak_evil_end"),
            "max_streak_sleepy": stats.get("max_streak_sleepy", 0),
            "max_streak_sleepy_start": stats.get("max_streak_sleepy_start"),
            "max_streak_sleepy_end": stats.get("max_streak_sleepy_end"),
            "duels_played": stats.get("duels_played", 0),
            "duels_won": stats.get("duels_won", 0),
            "duels_points_won": stats.get("duels_points_won", 0),
            "lottery_played": stats.get("lottery_played", 0),
            "lottery_won": stats.get("lottery_won", 0),
            "lottery_points_won": stats.get("lottery_points_won", 0),
            "daily_games": ctx.db.get_daily_games_today(message.chat.id, message.from_user.id, today_str(ctx.tz)),
            "current_streak_daily_max": stats.get("current_streak_daily_max", 0),
            "max_streak_daily_max": stats.get("max_streak_daily_max", 0),
            "last_daily_max_date": stats.get("last_daily_max_date"),
        }

        bg_path = ctx.config.get("images", {}).get("profile_bg", "images/profile_bg.png")
        keyboard = get_profile_keyboard(message.from_user.id, current_page="wins")
        caption_text = build_profile_caption(user_data, current_page="wins")
        sent = None

        try:
            card_bytes, file_id = await get_or_render_card(
                ctx.bot, message.chat.id, user_data, bg_path=bg_path, page="wins"
            )

            # Uniform format: Photo with duplicate formatted caption and custom emoji buttons
            if file_id:
                try:
                    sent = await message.answer_photo(
                        photo=file_id,
                        caption=caption_text,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )
                except Exception as e_fid:
                    logger.debug("Sending with cached file_id failed, fallback to bytes: %s", e_fid)
                    sent = None

            if not sent:
                photo_file = BufferedInputFile(card_bytes, filename=f"profile_{message.from_user.id}.png")
                sent = await message.answer_photo(
                    photo=photo_file,
                    caption=caption_text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )

            if sent and sent.photo:
                update_cached_file_id(message.chat.id, message.from_user.id, "wins", sent.photo[-1].file_id)

        except Exception as e:
            logger.error("Failed to render or send profile card image: %s", e, exc_info=True)
            sent = await message.answer(caption_text, parse_mode="HTML", reply_markup=keyboard)

        if sent:
            try:
                ctx.db.register_message_for_cleanup(
                    message.chat.id,
                    sent.chat.id,
                    sent.message_id,
                    datetime.now().isoformat(),
                    is_event=0,
                )
            except Exception as e:
                logger.error("Failed to register cleanup: %s", e)

    @router.callback_query(F.data.startswith("prof:"))
    async def on_profile_tab(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        if len(parts) != 3:
            await callback.answer()
            return

        target_user_id = int(parts[1])
        page = parts[2]

        chat_id = callback.message.chat.id
        stats = ctx.db.get_user_stats(chat_id, target_user_id)
        if not stats:
            await callback.answer("Данные профиля не найдены.", show_alert=True)
            return

        display_name = format_user_name(
            target_user_id,
            stats.get("username"),
            stats.get("first_name"),
            stats.get("last_name"),
        )

        bets_played = stats["bets_played"]
        bets_won = stats["bets_won"]
        open_bets = ctx.db.count_open_bets(chat_id, target_user_id, today_str(ctx.tz))

        user_data = {
            "display_name": display_name,
            "username": stats.get("username") or "",
            "user_id": target_user_id,
            "points": stats["points"],
            "wins_day": stats["wins_day"],
            "wins_evil": stats["wins_evil"],
            "wins_sleepy": stats["wins_sleepy"],
            "bets_played": bets_played,
            "bets_won": bets_won,
            "open_bets": open_bets,
            "max_streak_day": stats.get("max_streak_day", 0),
            "max_streak_day_start": stats.get("max_streak_day_start"),
            "max_streak_day_end": stats.get("max_streak_day_end"),
            "max_streak_evil": stats.get("max_streak_evil", 0),
            "max_streak_evil_start": stats.get("max_streak_evil_start"),
            "max_streak_evil_end": stats.get("max_streak_evil_end"),
            "max_streak_sleepy": stats.get("max_streak_sleepy", 0),
            "max_streak_sleepy_start": stats.get("max_streak_sleepy_start"),
            "max_streak_sleepy_end": stats.get("max_streak_sleepy_end"),
            "duels_played": stats.get("duels_played", 0),
            "duels_won": stats.get("duels_won", 0),
            "duels_points_won": stats.get("duels_points_won", 0),
            "lottery_played": stats.get("lottery_played", 0),
            "lottery_won": stats.get("lottery_won", 0),
            "lottery_points_won": stats.get("lottery_points_won", 0),
            "daily_games": ctx.db.get_daily_games_today(chat_id, target_user_id, today_str(ctx.tz)),
            "current_streak_daily_max": stats.get("current_streak_daily_max", 0),
            "max_streak_daily_max": stats.get("max_streak_daily_max", 0),
            "last_daily_max_date": stats.get("last_daily_max_date"),
        }

        bg_path = ctx.config.get("images", {}).get("profile_bg", "images/profile_bg.png")
        keyboard = get_profile_keyboard(target_user_id, current_page=page)
        caption_text = build_profile_caption(user_data, current_page=page)

        card_bytes, file_id = await get_or_render_card(
            ctx.bot, chat_id, user_data, bg_path=bg_path, page=page
        )

        edited = False
        if file_id:
            try:
                await callback.message.edit_media(
                    media=InputMediaPhoto(
                        media=file_id,
                        caption=caption_text,
                        parse_mode="HTML",
                    ),
                    reply_markup=keyboard,
                )
                edited = True
                await callback.answer()
            except Exception as e_fid:
                logger.debug("Edit with cached file_id failed, fallback to bytes: %s", e_fid)

        if not edited:
            try:
                photo_file = BufferedInputFile(card_bytes, filename=f"profile_{target_user_id}_{page}.png")
                res = await callback.message.edit_media(
                    media=InputMediaPhoto(
                        media=photo_file,
                        caption=caption_text,
                        parse_mode="HTML",
                    ),
                    reply_markup=keyboard,
                )
                if res and getattr(res, "photo", None):
                    update_cached_file_id(chat_id, target_user_id, page, res.photo[-1].file_id)
                await callback.answer()
            except Exception as e:
                logger.debug("Failed to edit profile media: %s", e)
                await callback.answer()

    return router


