import asyncio
import html
import io
import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from handlers.profile import fetch_user_avatar
from utils.bet_card import render_bet_card
from utils.card_cache import get_cached_general, set_cached_general, update_cached_general_file_id
from utils.context import AppContext
from utils.custom_emojis import fmt_emoji, get_emoji_id
from utils.guards import ensure_group_message, ensure_participant, ensure_supported_group
from utils.helpers import compute_coef, format_leaderboard_user_name, format_user_label, format_user_name, has_user_display_name
from utils.member import resolve_user_display
from utils.texts import bet_title
from utils.time_utils import today_str

logger = logging.getLogger(__name__)


def build_bet_caption(
    candidates: list[dict],
    group_id: int,
    owner_id: int,
    bet_type: str,
    bet_date: str,
    ctx: AppContext,
) -> str:
    is_day = bet_type == "day"
    crown_e = fmt_emoji("crown", "👑") if is_day else fmt_emoji("evil", "😈")
    coin_e = fmt_emoji("coin", "🪙")
    fire_e = fmt_emoji("fire", "🔥")
    title_label = "ДРАКОН ДНЯ" if is_day else "ЗЛОЙ ДРАКОН"
    user_points = ctx.db.get_points(group_id, owner_id)
    user_bets = ctx.db.get_user_bets_on_type(group_id, owner_id, bet_type, bet_date)

    if not user_bets:
        bet_status_str = "Ваша ставка: <i>не установлена</i>"
    elif len(user_bets) == 1:
        user_bet = user_bets[0]
        target_id = user_bet["target_user_id"]
        amt = user_bet["amount"]
        target_cand = next((c for c in candidates if c["user_id"] == target_id), None)
        target_name = target_cand["display_name"] if target_cand else f"ID {target_id}"
        bet_status_str = f"Ваша ставка: <b>{amt:,} 🪙 на {html.escape(target_name)}</b>".replace(",", " ")
    else:
        total_amt = sum(b["amount"] for b in user_bets)
        items = []
        for b in user_bets:
            target_id = b["target_user_id"]
            amt = b["amount"]
            target_cand = next((c for c in candidates if c["user_id"] == target_id), None)
            target_name = target_cand["display_name"] if target_cand else f"ID {target_id}"
            items.append(f"<b>{html.escape(target_name)}</b> — <b>{amt:,} 🪙</b>".replace(",", " "))
        bet_status_str = f"Ваши ставки (всего <b>{total_amt:,} 🪙</b>):\n  ▫️ " + "\n  ▫️ ".join(items)

    lines = [
        f"{crown_e} <b>СТАВКИ: {title_label}</b>",
        "────────────────────",
        f"📅 <b>Дата:</b> {bet_date}",
        f"👥 <b>Претендентов в пуле:</b> {len(candidates)}",
        f"{coin_e} <b>Ваш баланс:</b> {user_points:,} очков".replace(",", " "),
        f"{fire_e} {bet_status_str}",
        "────────────────────",
        "🎯 <b>Претенденты в пуле:</b>",
    ]

    for idx, c in enumerate(candidates, start=1):
        name = html.escape(c["display_name"])
        coef = c.get("coef", 2.0)
        coef_str = f"x{coef:.1f}" if coef == round(coef, 1) else f"x{coef:.2f}"
        total_b = c.get("total_bets", 0)
        bets_part = f"банк: {total_b:,} 🪙".replace(",", " ") if total_b > 0 else "ставок нет"
        lines.append(f"<b>{idx}.</b> <b>{name}</b> — <b>{coef_str}</b> ({bets_part})")

    lines.append("────────────────────")
    lines.append("<i>Нажмите на кандидата ниже, чтобы сделать или изменить ставку:</i>")
    return "\n".join(lines)


def build_bet_keyboard(
    candidates: list[dict],
    group_id: int,
    owner_id: int,
    bet_type: str,
    has_user_bet: bool,
) -> InlineKeyboardMarkup:
    keyboard = []
    row: list[InlineKeyboardButton] = []
    for idx, c in enumerate(candidates, start=1):
        name = c["display_name"]
        coef = c.get("coef", 2.0)
        coef_str = f"x{coef:.1f}" if coef == round(coef, 1) else f"x{coef:.2f}"
        clean_name = name if len(name) <= 14 else name[:13] + "…"
        label = f"{idx}. {clean_name} ({coef_str})"
        row.append(
            InlineKeyboardButton(
                text=label,
                callback_data=f"bpick:{group_id}:{owner_id}:{bet_type}:{c['user_id']}",
            )
        )
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    actions_row = []
    if has_user_bet:
        actions_row.append(
            InlineKeyboardButton(
                text="❌ Снять ставку",
                callback_data=f"bcnc:{group_id}:{owner_id}:{bet_type}",
            )
        )
    actions_row.append(
        InlineKeyboardButton(
            text="🔄 Обновить",
            callback_data=f"bref:{group_id}:{owner_id}:{bet_type}",
        )
    )
    keyboard.append(actions_row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_adjust_keyboard(
    group_id: int,
    owner_id: int,
    bet_type: str,
    target_id: int,
    desired_amount: int,
    step: int,
) -> InlineKeyboardMarkup:
    coin_emoji_id = get_emoji_id("coin")
    apply_text = f"✅ Поставить {desired_amount}" if coin_emoji_id else f"✅ Поставить {desired_amount} 🪙"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"-{step}",
                    callback_data=f"bamt:{group_id}:{owner_id}:{bet_type}:{target_id}:{max(0, desired_amount - step)}",
                ),
                InlineKeyboardButton(
                    text=f"+{step}",
                    callback_data=f"bamt:{group_id}:{owner_id}:{bet_type}:{target_id}:{desired_amount + step}",
                ),
                InlineKeyboardButton(
                    text=f"-{step * 5}",
                    callback_data=f"bamt:{group_id}:{owner_id}:{bet_type}:{target_id}:{max(0, desired_amount - step * 5)}",
                ),
                InlineKeyboardButton(
                    text=f"+{step * 5}",
                    callback_data=f"bamt:{group_id}:{owner_id}:{bet_type}:{target_id}:{desired_amount + step * 5}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=apply_text,
                    icon_custom_emoji_id=coin_emoji_id,
                    callback_data=f"bapply:{group_id}:{owner_id}:{bet_type}:{target_id}:{desired_amount}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад к пулу",
                    callback_data=f"bback:{group_id}:{owner_id}:{bet_type}",
                )
            ],
        ]
    )


async def get_or_render_pool_card(
    ctx: AppContext,
    group_id: int,
    bet_type: str,
    bet_date: str,
    candidates: list[dict],
    total_participants: int,
) -> tuple[bytes, str | None, str]:
    cache_key = f"bet_pool_card:{group_id}:{bet_type}:{bet_date}"
    cached = get_cached_general(cache_key)
    if cached is not None:
        card_bytes, file_id = cached
        return card_bytes, file_id, cache_key

    for c in candidates:
        c["avatar_bytes"] = await fetch_user_avatar(ctx.bot, c["user_id"])

    buf = render_bet_card(
        candidates=candidates,
        bet_type=bet_type,
        bet_date=bet_date,
        min_bet=ctx.config.get("bet_step", 10),
        total_participants=total_participants,
    )
    card_bytes = buf.getvalue()
    # Cache for the whole day (24 hours) since pool candidates don't change within the day
    set_cached_general(cache_key, card_bytes, ttl=86400)
    return card_bytes, None, cache_key


def get_router(ctx: AppContext) -> Router:
    router = Router()

    async def send_bet_pool_menu(
        target: Message | CallbackQuery,
        group_id: int,
        owner_id: int,
        bet_type: str,
    ) -> None:
        bet_date = today_str(ctx.tz)
        all_participants = ctx.db.list_participants(group_id)
        if not all_participants:
            text = f"Ставки на {bet_title(bet_type)}\n\nПока нет участников в игре."
            if isinstance(target, CallbackQuery):
                if target.message:
                    try:
                        await target.message.edit_caption(caption=text)
                    except Exception:
                        await target.message.answer(text)
            else:
                await target.answer(text)
            return

        raw_candidates = ctx.db.get_or_create_bet_pool(
            group_id, bet_type, bet_date, ctx.config, all_participants
        )
        candidates = []
        for c in raw_candidates:
            u_name, f_name, l_name = await resolve_user_display(
                ctx,
                group_id,
                c["user_id"],
                c.get("username"),
                c.get("first_name"),
                c.get("last_name"),
            )
            # Use non-pinging user name (like in leaderboard)
            display_name = format_leaderboard_user_name(c["user_id"], u_name, f_name, l_name)
            stats = ctx.db.get_user_stats(group_id, c["user_id"]) or {}
            wins_total = stats.get("wins_day", 0) + stats.get("wins_evil", 0) + stats.get("wins_sleepy", 0)
            coef = compute_coef(wins_total, ctx.config)
            total_bets = ctx.db.get_total_bets_for_candidate(group_id, bet_type, c["user_id"], bet_date)
            candidates.append({
                "user_id": c["user_id"],
                "username": u_name,
                "first_name": f_name,
                "last_name": l_name,
                "display_name": display_name,
                "coef": coef,
                "total_bets": total_bets,
            })

        user_bets = ctx.db.get_user_bets_on_type(group_id, owner_id, bet_type, bet_date)
        has_user_bet = len(user_bets) > 0
        caption_text = build_bet_caption(candidates, group_id, owner_id, bet_type, bet_date, ctx)
        keyboard = build_bet_keyboard(candidates, group_id, owner_id, bet_type, has_user_bet)

        card_bytes, file_id, cache_key = await get_or_render_pool_card(
            ctx, group_id, bet_type, bet_date, candidates, len(all_participants)
        )

        if isinstance(target, CallbackQuery):
            msg = target.message
            if msg and msg.photo:
                # Fast path: already has photo, simply update caption without re-uploading media
                try:
                    await msg.edit_caption(caption=caption_text, parse_mode="HTML", reply_markup=keyboard)
                except TelegramBadRequest as e:
                    if "message is not modified" not in str(e):
                        logger.debug("edit_caption failed: %s", e)
                except Exception as e:
                    logger.debug("edit_caption failed, fallback to edit_media: %s", e)
                    media = file_id if file_id else BufferedInputFile(card_bytes, filename=f"pool_{bet_type}_{group_id}.png")
                    try:
                        res = await msg.edit_media(
                            media=InputMediaPhoto(media=media, caption=caption_text, parse_mode="HTML"),
                            reply_markup=keyboard,
                        )
                        if res and getattr(res, "photo", None):
                            update_cached_general_file_id(cache_key, res.photo[-1].file_id)
                    except Exception:
                        pass
            elif msg:
                sent = None
                if file_id:
                    try:
                        sent = await msg.answer_photo(
                            photo=file_id,
                            caption=caption_text,
                            parse_mode="HTML",
                            reply_markup=keyboard,
                        )
                    except Exception:
                        sent = None
                if not sent:
                    photo_file = BufferedInputFile(card_bytes, filename=f"pool_{bet_type}_{group_id}.png")
                    sent = await msg.answer_photo(photo_file, caption=caption_text, parse_mode="HTML", reply_markup=keyboard)
                if sent and sent.photo:
                    update_cached_general_file_id(cache_key, sent.photo[-1].file_id)
                if sent:
                    ctx.db.register_message_for_cleanup(group_id, sent.chat.id, sent.message_id, datetime.now().isoformat())
        else:
            # Initial command /bet_day or /bet_evil
            sent = None
            if file_id:
                try:
                    sent = await target.answer_photo(
                        photo=file_id,
                        caption=caption_text,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )
                except Exception as e_fid:
                    logger.debug("Sending with cached file_id failed: %s", e_fid)
                    sent = None

            if not sent:
                photo_file = BufferedInputFile(card_bytes, filename=f"pool_{bet_type}_{group_id}.png")
                sent = await target.answer_photo(
                    photo=photo_file,
                    caption=caption_text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )

            if sent and sent.photo:
                update_cached_general_file_id(cache_key, sent.photo[-1].file_id)

            if sent:
                ctx.db.register_message_for_cleanup(group_id, sent.chat.id, sent.message_id, datetime.now().isoformat())

    @router.message(Command("bet_day"))
    async def cmd_bet_day(message: Message) -> None:
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
        await send_bet_pool_menu(message, message.chat.id, message.from_user.id, "day")

    @router.message(Command("bet_evil"))
    async def cmd_bet_evil(message: Message) -> None:
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
        await send_bet_pool_menu(message, message.chat.id, message.from_user.id, "evil")

    @router.callback_query(F.data.startswith("bpick:"))
    async def cb_bpick(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        owner_id = int(parts[2])
        bet_type = parts[3]
        target_id = int(parts[4])

        if callback.from_user.id != owner_id:
            await callback.answer("Эти кнопки только для автора команды.", show_alert=True)
            return
        if not await ensure_supported_group(ctx, callback):
            return

        bet_date = today_str(ctx.tz)
        target = ctx.db.get_user_identity(group_id, target_id)
        u_name, f_name, l_name = await resolve_user_display(
            ctx,
            group_id,
            target_id,
            target.get("username") if target else None,
            target.get("first_name") if target else None,
            target.get("last_name") if target else None,
        )
        name = html.escape(format_leaderboard_user_name(target_id, u_name, f_name, l_name))
        stats = ctx.db.get_user_stats(group_id, target_id) or {}
        wins_total = stats.get("wins_day", 0) + stats.get("wins_evil", 0) + stats.get("wins_sleepy", 0)
        coef = compute_coef(wins_total, ctx.config)

        current_amount = ctx.db.get_bet_amounts(group_id, owner_id, bet_type, bet_date).get(target_id, 0)
        step = ctx.config.get("bet_step", 10)
        desired_amount = max(step, current_amount)
        payout = int(desired_amount * coef)
        user_points = ctx.db.get_points(group_id, owner_id)

        adjust_caption = (
            f"🎯 <b>Ставка на {bet_title(bet_type)}</b>\n"
            f"────────────────────\n"
            f"👤 <b>Кандидат:</b> {name}\n"
            f"📈 <b>Коэффициент:</b> x{coef:.2f}\n"
            f"🪙 <b>Ваш баланс:</b> {user_points:,} очков\n\n"
            f"Текущая ставка: <b>{current_amount:,}</b> 🪙\n"
            f"Выбранная сумма: <b>{desired_amount:,}</b> 🪙\n"
            f"Возможный выигрыш: <b>+{payout:,}</b> 🪙\n"
            f"────────────────────\n"
            f"<i>Выберите сумму и подтвердите ставку:</i>"
        ).replace(",", " ")

        keyboard = build_adjust_keyboard(group_id, owner_id, bet_type, target_id, desired_amount, step)
        if callback.message:
            try:
                await callback.message.edit_caption(caption=adjust_caption, parse_mode="HTML", reply_markup=keyboard)
            except Exception:
                pass
        await callback.answer()

    @router.callback_query(F.data.startswith("bamt:"))
    async def cb_bamt(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        owner_id = int(parts[2])
        bet_type = parts[3]
        target_id = int(parts[4])
        desired_amount = max(0, int(parts[5]))

        if callback.from_user.id != owner_id:
            await callback.answer("Эти кнопки только для автора команды.", show_alert=True)
            return

        bet_date = today_str(ctx.tz)
        target = ctx.db.get_user_identity(group_id, target_id)
        u_name, f_name, l_name = await resolve_user_display(
            ctx,
            group_id,
            target_id,
            target.get("username") if target else None,
            target.get("first_name") if target else None,
            target.get("last_name") if target else None,
        )
        name = html.escape(format_leaderboard_user_name(target_id, u_name, f_name, l_name))
        stats = ctx.db.get_user_stats(group_id, target_id) or {}
        wins_total = stats.get("wins_day", 0) + stats.get("wins_evil", 0) + stats.get("wins_sleepy", 0)
        coef = compute_coef(wins_total, ctx.config)

        current_amount = ctx.db.get_bet_amounts(group_id, owner_id, bet_type, bet_date).get(target_id, 0)
        step = ctx.config.get("bet_step", 10)
        payout = int(desired_amount * coef)
        user_points = ctx.db.get_points(group_id, owner_id)

        adjust_caption = (
            f"🎯 <b>Ставка на {bet_title(bet_type)}</b>\n"
            f"────────────────────\n"
            f"👤 <b>Кандидат:</b> {name}\n"
            f"📈 <b>Коэффициент:</b> x{coef:.2f}\n"
            f"🪙 <b>Ваш баланс:</b> {user_points:,} очков\n\n"
            f"Текущая ставка: <b>{current_amount:,}</b> 🪙\n"
            f"Выбранная сумма: <b>{desired_amount:,}</b> 🪙\n"
            f"Возможный выигрыш: <b>+{payout:,}</b> 🪙\n"
            f"────────────────────\n"
            f"<i>Выберите сумму и подтвердите ставку:</i>"
        ).replace(",", " ")

        keyboard = build_adjust_keyboard(group_id, owner_id, bet_type, target_id, desired_amount, step)
        if callback.message:
            try:
                await callback.message.edit_caption(caption=adjust_caption, parse_mode="HTML", reply_markup=keyboard)
            except Exception:
                pass
        await callback.answer()

    @router.callback_query(F.data.startswith("bapply:"))
    async def cb_bapply(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        owner_id = int(parts[2])
        bet_type = parts[3]
        target_id = int(parts[4])
        desired_amount = int(parts[5])

        if callback.from_user.id != owner_id:
            await callback.answer("Эти кнопки только для автора команды.", show_alert=True)
            return
        if not await ensure_supported_group(ctx, callback):
            return

        bet_date = today_str(ctx.tz)
        current_amount = ctx.db.get_bet_amounts(group_id, owner_id, bet_type, bet_date).get(target_id, 0)
        delta = desired_amount - current_amount
        if delta == 0:
            await callback.answer("Ставка уже установлена на эту сумму.")
            await send_bet_pool_menu(callback, group_id, owner_id, bet_type)
            return

        ok, error = ctx.db.adjust_bet(group_id, owner_id, bet_type, target_id, bet_date, delta)
        if not ok:
            await callback.answer(error, show_alert=True)
            return

        await callback.answer(f"✅ Ставка {desired_amount} 🪙 сохранена!", show_alert=False)
        await send_bet_pool_menu(callback, group_id, owner_id, bet_type)

    @router.callback_query(F.data.startswith("bcnc:"))
    async def cb_bcnc(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        owner_id = int(parts[2])
        bet_type = parts[3]

        if callback.from_user.id != owner_id:
            await callback.answer("Эти кнопки только для автора команды.", show_alert=True)
            return

        bet_date = today_str(ctx.tz)
        refunded = ctx.db.cancel_bets(group_id, owner_id, bet_type, bet_date)

        await callback.answer(f"Ставка отменена, возвращено {refunded} 🪙", show_alert=True)
        await send_bet_pool_menu(callback, group_id, owner_id, bet_type)

    @router.callback_query(F.data.startswith("bback:"))
    async def cb_bback(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        owner_id = int(parts[2])
        bet_type = parts[3]

        if callback.from_user.id != owner_id:
            await callback.answer("Эти кнопки только для автора команды.", show_alert=True)
            return

        await send_bet_pool_menu(callback, group_id, owner_id, bet_type)
        await callback.answer()

    @router.callback_query(F.data.startswith("bref:"))
    async def cb_bref(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        owner_id = int(parts[2])
        bet_type = parts[3]

        if callback.from_user.id != owner_id:
            await callback.answer("Эти кнопки только для автора команды.", show_alert=True)
            return

        await send_bet_pool_menu(callback, group_id, owner_id, bet_type)
        await callback.answer("Обновлено!")

    @router.message(Command("cancel_day"))
    async def cmd_cancel_day(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        if not message.from_user:
            return
        if not await ensure_participant(ctx, message):
            return
        refunded = ctx.db.cancel_bets(message.chat.id, message.from_user.id, "day", today_str(ctx.tz))
        await message.answer(f"Ставки на Дракона Дня отменены, возвращено очков: {refunded}.")

    @router.message(Command("cancel_evil"))
    async def cmd_cancel_evil(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        if not message.from_user:
            return
        if not await ensure_participant(ctx, message):
            return
        refunded = ctx.db.cancel_bets(message.chat.id, message.from_user.id, "evil", today_str(ctx.tz))
        await message.answer(f"Ставки на Злого Дракона отменены, возвращено очков: {refunded}.")

    @router.message(Command("my_bets"))
    async def cmd_my_bets(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        if not message.from_user:
            return
        if not await ensure_participant(ctx, message):
            return
        ctx.db.sync_user(
            message.chat.id,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        bet_date = today_str(ctx.tz)
        bets = ctx.db.list_active_bets(message.chat.id, message.from_user.id, bet_date)
        if not bets:
            await message.answer("Активных ставок нет.")
            return
        lines = ["🎯 <b>Ваши активные ставки на сегодня:</b>", ""]
        for bet in bets:
            target = ctx.db.get_user_identity(message.chat.id, bet["target_user_id"])
            username = target.get("username") if target else None
            first_name = target.get("first_name") if target else None
            last_name = target.get("last_name") if target else None
            if not has_user_display_name(username, first_name, last_name):
                u_name, f_name, l_name = await resolve_user_display(ctx, message.chat.id, bet["target_user_id"])
                if u_name or f_name or l_name:
                    username, first_name, last_name = u_name, f_name, l_name
            name = html.escape(
                format_leaderboard_user_name(
                    bet["target_user_id"],
                    username,
                    first_name,
                    last_name,
                )
            )
            stats = ctx.db.get_user_stats(message.chat.id, bet["target_user_id"]) or {}
            wins_total = stats.get("wins_day", 0) + stats.get("wins_evil", 0) + stats.get("wins_sleepy", 0)
            coef = compute_coef(wins_total, ctx.config)
            payout = int(bet["amount"] * coef)
            lines.append(
                f"• {bet_title(bet['bet_type'])}: <b>{name}</b> — <b>{bet['amount']} 🪙</b> "
                f"(коэф. x{coef:.2f}, выигрыш: +{payout} 🪙)"
            )
        await message.answer("\n".join(lines), parse_mode="HTML")

    return router
