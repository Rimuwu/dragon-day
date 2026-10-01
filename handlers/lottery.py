import asyncio
import io
import logging
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from utils.card_cache import (
    get_cached_general,
    invalidate_user_cache,
    set_cached_general,
    update_cached_general_file_id,
)
from utils.context import AppContext
from utils.custom_emojis import fmt_emoji, get_emoji_id
from utils.guards import ensure_group_message, ensure_participant, ensure_supported_group
from utils.helpers import format_user_name
from utils.lottery_card import render_lottery_card

logger = logging.getLogger(__name__)


def _render_lottery(lottery_info: dict, winning_ticket: int | None = None) -> io.BytesIO:
    """Render lottery card from lottery_info dict returned by storage."""
    sold_tickets = lottery_info.get("sold_tickets", [])
    bet = lottery_info["bet"]
    prize = len(sold_tickets) * bet
    return render_lottery_card(
        prize=prize,
        ticket_price=bet,
        sold_count=len(sold_tickets),
        sold_tickets=sold_tickets,
        winning_ticket=winning_ticket,
    )


def build_lottery_caption(lottery: dict, remaining_str: str) -> str:
    coin_e = fmt_emoji("coin", "🪙")
    fire_e = fmt_emoji("fire", "🔥")
    bet = lottery["bet"]
    sold_tickets = lottery.get("sold_tickets", [])
    sold_count = len(sold_tickets)
    total_bank = sold_count * bet
    participants_count = len(lottery.get("participants", []))

    return (
        f"🎟️ <b>КОРОЛЕВСКАЯ ЛОТЕРЕЯ #{lottery['id']}</b>\n"
        f"────────────────────\n"
        f"{coin_e} <b>Цена билета:</b> {bet:,} очков\n"
        f"{fire_e} <b>Призовой фонд:</b> {total_bank:,} очков\n"
        f"👥 <b>Участников:</b> {participants_count} (билетов: {sold_count}/100)\n"
        f"⏳ <b>До подведения итогов:</b> {remaining_str}\n"
        f"────────────────────\n"
        f"💡 <b>Купить номер:</b> напишите <code>/lottery &lt;номер&gt;</code> (например: <code>/lottery 42</code>)\n"
        f"🎲 Или нажмите кнопку ниже, чтобы получить случайный билет!\n"
        f"<i>Призовой фонд равен сумме всех вложенных очков. Победитель забирает всё!</i>"
    ).replace(",", " ")


def build_lottery_keyboard(lottery_id: int, bet: int) -> InlineKeyboardMarkup:
    coin_emoji_id = get_emoji_id("coin")
    buy_text = f"🎲 Случайный билет ({bet} очков)" if coin_emoji_id else f"🎲 Случайный билет ({bet} 🪙)"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=buy_text,
                    icon_custom_emoji_id=coin_emoji_id,
                    callback_data=f"lot_buy:{lottery_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Обновить статус",
                    callback_data=f"lot_ref:{lottery_id}",
                ),
            ],
        ]
    )


def build_lottery_ranges_keyboard(lottery_id: int, sold_tickets: list[int]) -> InlineKeyboardMarkup:
    sold_set = set(sold_tickets)
    ranges = [
        (1, 20, "01 — 20"),
        (21, 40, "21 — 40"),
        (41, 60, "41 — 60"),
        (61, 80, "61 — 80"),
        (81, 100, "81 — 100"),
    ]
    buttons = []
    row = []
    for start, end, label in ranges:
        avail_count = sum(1 for t in range(start, end + 1) if t not in sold_set)
        btn_text = f"[{label}] ({avail_count} своб.)"
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"lot_page:{lottery_id}:{start}-{end}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton(text="« Назад в лотерею", callback_data=f"lot_ref:{lottery_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_lottery_tickets_grid_keyboard(lottery_id: int, start: int, end: int, sold_tickets: list[int]) -> InlineKeyboardMarkup:
    sold_set = set(sold_tickets)
    buttons = []
    current_row = []

    for num in range(start, end + 1):
        if num in sold_set:
            btn = InlineKeyboardButton(text=f"❌ {num:02d}", callback_data=f"lot_sold:{num}")
        else:
            btn = InlineKeyboardButton(text=f"🎟️ {num:02d}", callback_data=f"lot_num:{lottery_id}:{num}")
        current_row.append(btn)
        if len(current_row) == 5:
            buttons.append(current_row)
            current_row = []
    if current_row:
        buttons.append(current_row)

    buttons.append([
        InlineKeyboardButton(text="« Выбор диапазона", callback_data=f"lot_pick:{lottery_id}:ranges"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data=f"lot_ref:{lottery_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_remaining_time(closes_at_str: str) -> str:
    try:
        closes_at = datetime.fromisoformat(closes_at_str)
        now = datetime.now()
        diff = closes_at - now
        if diff.total_seconds() <= 0:
            return "Итоги подводятся..."
        total_seconds = int(diff.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 0:
            return f"{hours} ч. {minutes} мин."
        return f"{minutes} мин."
    except Exception:
        return "2 часа"


def get_router(ctx: AppContext) -> Router:
    router = Router()

    @router.message(Command("lottery"))
    async def cmd_lottery(message: Message, command: CommandObject) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return

        chat_id = message.chat.id
        user = message.from_user
        if not user:
            return
        if not await ensure_participant(ctx, message):
            return

        ctx.db.sync_user(
            chat_id,
            user.id,
            user.username,
            user.first_name,
            user.last_name,
        )

        active = ctx.db.get_active_lottery(chat_id)
        if active:
            raw_args = (command.args or "").strip()
            # If user provided ticket number to buy, e.g. "/lottery 42" or "/lottery buy 42"
            chosen_num = None
            if raw_args:
                for tok in raw_args.split():
                    clean_tok = tok.lstrip("#")
                    if clean_tok.isdigit():
                        cand = int(clean_tok)
                        if 1 <= cand <= 100:
                            chosen_num = cand
                            break

            if chosen_num is not None:
                ok, msg, ticket_num = ctx.db.join_lottery(active["id"], user.id, chosen_ticket=chosen_num)
                if not ok:
                    await message.answer(f"❌ {msg}")
                    return
                invalidate_user_cache(chat_id, user.id)
                await message.answer(f"🎟️ {msg}")

                # Refresh card
                lottery_info = ctx.db.get_lottery(active["id"])
                if lottery_info:
                    rem = format_remaining_time(lottery_info["closes_at"])
                    caption = build_lottery_caption(lottery_info, rem)
                    keyboard = build_lottery_keyboard(lottery_info["id"], lottery_info["bet"])
                    card_buf = _render_lottery(lottery_info)
                    count = len(lottery_info.get("participants", []))
                    photo = BufferedInputFile(
                        card_buf.getvalue(),
                        filename=f"lottery_{lottery_info['id']}_{count}_{int(datetime.now().timestamp())}.png",
                    )
                    sent = await message.answer_photo(photo=photo, caption=caption, parse_mode="HTML", reply_markup=keyboard)
                    if sent:
                        ctx.db.register_message_for_cleanup(chat_id, sent.chat.id, sent.message_id, datetime.now().isoformat())
                return

            # Active lottery already exists: send current status card
            rem = format_remaining_time(active["closes_at"])
            caption = build_lottery_caption(active, rem)
            keyboard = build_lottery_keyboard(active["id"], active["bet"])

            card_buf = _render_lottery(active)
            count = len(active.get("participants", []))
            photo = BufferedInputFile(
                card_buf.getvalue(),
                filename=f"lottery_{active['id']}_{count}_{int(datetime.now().timestamp())}.png",
            )
            sent = await message.answer_photo(photo=photo, caption=caption, parse_mode="HTML", reply_markup=keyboard)
            if sent:
                ctx.db.register_message_for_cleanup(chat_id, sent.chat.id, sent.message_id, datetime.now().isoformat())
            return

        # Parse bet and optional creator ticket
        raw_args = (command.args or "").strip()
        bet = 100
        creator_ticket = None
        if raw_args:
            parts = raw_args.split()
            try:
                bet = int(parts[0])
            except ValueError:
                await message.answer("❌ Укажите корректную сумму ставки. Пример: <code>/lottery 100</code> или <code>/lottery 100 42</code>")
                return
            if len(parts) > 1 and parts[1].lstrip("#").isdigit():
                cand = int(parts[1].lstrip("#"))
                if 1 <= cand <= 100:
                    creator_ticket = cand

        if bet < 10:
            await message.answer("❌ Минимальная цена билета в лотерее — 10 очков.")
            return
        if bet > 500_000:
            await message.answer("❌ Максимальная цена билета в лотерее — 500 000 очков.")
            return

        # Closes in 2 hours
        closes_at = (datetime.now() + timedelta(hours=2)).isoformat()
        lottery_id, err = ctx.db.create_lottery(
            group_id=chat_id,
            creator_id=user.id,
            bet=bet,
            closes_at=closes_at,
            creator_ticket=creator_ticket,
        )
        if lottery_id is None:
            await message.answer(f"❌ {err}")
            return

        invalidate_user_cache(chat_id, user.id)
        lottery_info = ctx.db.get_lottery(lottery_id)
        rem = format_remaining_time(closes_at)
        caption = build_lottery_caption(lottery_info, rem)
        keyboard = build_lottery_keyboard(lottery_id, bet)

        card_buf = _render_lottery(lottery_info)
        photo = BufferedInputFile(
            card_buf.getvalue(),
            filename=f"lottery_{lottery_id}_1_{int(datetime.now().timestamp())}.png",
        )
        sent = await message.answer_photo(
            photo=photo,
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        if sent:
            ctx.db.update_lottery_message_id(lottery_id, sent.message_id)
            ctx.db.register_message_for_cleanup(
                chat_id,
                sent.chat.id,
                sent.message_id,
                datetime.now().isoformat(),
            )

    @router.callback_query(F.data.startswith("lot_buy:"))
    async def cb_lottery_buy(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        if len(parts) != 2:
            await callback.answer()
            return

        lottery_id = int(parts[1])
        user = callback.from_user
        if not await ensure_participant(ctx, callback):
            return
        chat_id = callback.message.chat.id

        ctx.db.sync_user(
            chat_id,
            user.id,
            user.username,
            user.first_name,
            user.last_name,
        )

        ok, msg, ticket_num = ctx.db.join_lottery(lottery_id, user.id)
        if not ok:
            await callback.answer(msg, show_alert=True)
            return

        invalidate_user_cache(chat_id, user.id)
        await callback.answer(f"🎟️ {msg}", show_alert=True)

        # Update card & caption
        lottery_info = ctx.db.get_lottery(lottery_id)
        if not lottery_info:
            return

        rem = format_remaining_time(lottery_info["closes_at"])
        caption = build_lottery_caption(lottery_info, rem)
        keyboard = build_lottery_keyboard(lottery_id, lottery_info["bet"])

        card_buf = _render_lottery(lottery_info)
        count = len(lottery_info.get("participants", []))

        try:
            photo = BufferedInputFile(
                card_buf.getvalue(),
                filename=f"lottery_{lottery_id}_{count}_{int(datetime.now().timestamp())}.png",
            )
            await callback.message.edit_media(
                media=InputMediaPhoto(media=photo, caption=caption, parse_mode="HTML"),
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.debug("Failed to edit lottery card: %s", e)

    @router.callback_query(F.data.startswith("lot_pick:"))
    async def cb_lottery_pick_ranges(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        lottery_id = int(parts[1])
        lottery_info = ctx.db.get_lottery(lottery_id)
        if not lottery_info or lottery_info["status"] != "active":
            await callback.answer("Лотерея завершена или не найдена.", show_alert=True)
            return

        sold_tickets = lottery_info.get("sold_tickets", [])
        keyboard = build_lottery_ranges_keyboard(lottery_id, sold_tickets)
        try:
            await callback.message.edit_reply_markup(reply_markup=keyboard)
            await callback.answer("Выберите диапазон номеров:")
        except Exception:
            await callback.answer()

    @router.callback_query(F.data.startswith("lot_page:"))
    async def cb_lottery_page(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        lottery_id = int(parts[1])
        rng = parts[2].split("-")
        start, end = int(rng[0]), int(rng[1])
        lottery_info = ctx.db.get_lottery(lottery_id)
        if not lottery_info or lottery_info["status"] != "active":
            await callback.answer("Лотерея завершена или не найдена.", show_alert=True)
            return

        sold_tickets = lottery_info.get("sold_tickets", [])
        keyboard = build_lottery_tickets_grid_keyboard(lottery_id, start, end, sold_tickets)
        try:
            await callback.message.edit_reply_markup(reply_markup=keyboard)
            await callback.answer(f"Номера с {start:02d} по {end:02d}:")
        except Exception:
            await callback.answer()

    @router.callback_query(F.data.startswith("lot_sold:"))
    async def cb_lottery_sold(callback: CallbackQuery) -> None:
        num = int(callback.data.split(":")[1])
        await callback.answer(f"Билет №{num:03d} уже куплен другим игроком!", show_alert=True)

    @router.callback_query(F.data.startswith("lot_num:"))
    async def cb_lottery_buy_num(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        lottery_id = int(parts[1])
        num = int(parts[2])
        user = callback.from_user
        if not await ensure_participant(ctx, callback):
            return
        chat_id = callback.message.chat.id

        ctx.db.sync_user(
            chat_id,
            user.id,
            user.username,
            user.first_name,
            user.last_name,
        )

        ok, msg, ticket_num = ctx.db.join_lottery(lottery_id, user.id, chosen_ticket=num)
        if not ok:
            await callback.answer(msg, show_alert=True)
            return

        invalidate_user_cache(chat_id, user.id)
        await callback.answer(f"🎟️ {msg}", show_alert=True)

        lottery_info = ctx.db.get_lottery(lottery_id)
        if not lottery_info:
            return

        rem = format_remaining_time(lottery_info["closes_at"])
        caption = build_lottery_caption(lottery_info, rem)
        keyboard = build_lottery_keyboard(lottery_id, lottery_info["bet"])

        card_buf = _render_lottery(lottery_info)
        count = len(lottery_info.get("participants", []))

        try:
            photo = BufferedInputFile(
                card_buf.getvalue(),
                filename=f"lottery_{lottery_id}_{count}_{int(datetime.now().timestamp())}.png",
            )
            await callback.message.edit_media(
                media=InputMediaPhoto(media=photo, caption=caption, parse_mode="HTML"),
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.debug("Failed to edit lottery card: %s", e)

    @router.callback_query(F.data.startswith("lot_ref:"))
    async def cb_lottery_refresh(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        if len(parts) != 2:
            await callback.answer()
            return

        lottery_id = int(parts[1])
        lottery_info = ctx.db.get_lottery(lottery_id)
        if not lottery_info or lottery_info["status"] != "active":
            await callback.answer("Лотерея завершена или не найдена.", show_alert=True)
            return

        await callback.answer("Данные обновлены.")
        rem = format_remaining_time(lottery_info["closes_at"])
        caption = build_lottery_caption(lottery_info, rem)
        keyboard = build_lottery_keyboard(lottery_id, lottery_info["bet"])

        card_buf = _render_lottery(lottery_info)
        count = len(lottery_info.get("participants", []))

        try:
            photo = BufferedInputFile(
                card_buf.getvalue(),
                filename=f"lottery_{lottery_id}_{count}_{int(datetime.now().timestamp())}.png",
            )
            await callback.message.edit_media(
                media=InputMediaPhoto(media=photo, caption=caption, parse_mode="HTML"),
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.debug("Failed to refresh lottery: %s", e)

    return router
