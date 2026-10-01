import asyncio
import html
import io
import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from handlers.profile import fetch_user_avatar
from utils.context import AppContext
from utils.custom_emojis import fmt_emoji, get_emoji_id
from utils.duel_card import render_duel_card
from utils.guards import ensure_group_message, ensure_participant, ensure_supported_group
from utils.helpers import format_user_name

logger = logging.getLogger(__name__)


def get_router(ctx: AppContext) -> Router:
    router = Router()

    @router.message(Command("duel"))
    async def cmd_duel(message: Message, command: CommandObject) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return

        chat_id = message.chat.id
        creator = message.from_user
        if not creator:
            return
        if not await ensure_participant(ctx, message):
            return

        ctx.db.sync_user(
            chat_id,
            creator.id,
            creator.username,
            creator.first_name,
            creator.last_name,
        )

        # Parse bet
        raw_args = (command.args or "").strip()
        bet = 100
        if raw_args:
            try:
                bet = int(raw_args.split()[0])
            except ValueError:
                await message.answer("❌ Укажите корректную сумму ставки. Пример: <code>/duel 100</code>")
                return

        if bet < 10:
            await message.answer("❌ Минимальная ставка для дуэли — 10 очков.")
            return
        if bet > 1_000_000:
            await message.answer("❌ Максимальная ставка для дуэли — 1 000 000 очков.")
            return

        # Check target player (if replied to another message)
        target_user = None
        target_id = None
        target_name = None
        if message.reply_to_message and message.reply_to_message.from_user:
            replied = message.reply_to_message.from_user
            if replied.is_bot:
                await message.answer("❌ Нельзя вызвать на дуэль бота.")
                return
            if replied.id == creator.id:
                await message.answer("❌ Нельзя вызвать на дуэль самого себя.")
                return

            target_user = replied
            target_id = replied.id
            if not ctx.db.is_participant(chat_id, target_id):
                target_formatted = format_user_name(target_id, replied.username, replied.first_name, replied.last_name)
                await message.answer(
                    f"❌ <b>{target_formatted}</b> ещё не вступил(а) в игру! Игрок должен сначала написать /enter.",
                    parse_mode="HTML",
                )
                return

            ctx.db.sync_user(
                chat_id,
                target_id,
                replied.username,
                replied.first_name,
                replied.last_name,
            )
            target_name = format_user_name(target_id, replied.username, replied.first_name, replied.last_name)

        creator_name = format_user_name(creator.id, creator.username, creator.first_name, creator.last_name)

        # Create duel in DB (deducts bet from creator)
        duel_id, err = ctx.db.create_duel(
            group_id=chat_id,
            creator_id=creator.id,
            target_id=target_id,
            bet=bet,
        )
        if duel_id is None:
            await message.answer(f"❌ {err}")
            return

        dice_e = fmt_emoji("dice", "🎲")
        coin_e = fmt_emoji("coin", "🪙")
        fire_e = fmt_emoji("fire", "🔥")

        if target_id:
            opponent_line = f"🎯 <b>Вызов брошен:</b> {html.escape(target_name)}"
            accept_text = f"⚔️ Принять вызов ({bet} {coin_e})"
        else:
            opponent_line = "🎯 <b>Вызов:</b> Любому желающему!"
            accept_text = f"⚔️ Принять дуэль ({bet} {coin_e})"

        text = (
            f"⚔️ <b>ВЫЗОВ НА ДУЭЛЬ!</b>\n"
            f"────────────────────\n"
            f"👤 <b>Инициатор:</b> {html.escape(creator_name)}\n"
            f"{opponent_line}\n"
            f"{coin_e} <b>Ставка:</b> {bet:,} очков\n"
            f"{fire_e} <b>Банк победителя:</b> {bet * 2:,} очков\n"
            f"────────────────────\n"
            f"<i>Каждый игрок бросает по 2 кубика. Победитель с наибольшей суммой забирает банк!</i>"
        ).replace(",", " ")

        dice_emoji_id = get_emoji_id("dice")
        accept_text = f"Принять ({bet} очков)" if dice_emoji_id else f"⚔️ Принять ({bet} 🪙)"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=accept_text,
                        icon_custom_emoji_id=dice_emoji_id,
                        callback_data=f"duel_acc:{duel_id}",
                    ),
                    InlineKeyboardButton(
                        text="❌ Отменить",
                        callback_data=f"duel_cnc:{duel_id}",
                    ),
                ]
            ]
        )

        sent = await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
        if sent:
            ctx.db.update_duel_message_id(duel_id, sent.message_id)
            ctx.db.register_message_for_cleanup(
                chat_id,
                sent.chat.id,
                sent.message_id,
                datetime.now().isoformat(),
            )

    @router.callback_query(F.data.startswith("duel_cnc:"))
    async def cb_duel_cancel(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        if len(parts) != 2:
            await callback.answer()
            return

        duel_id = int(parts[1])
        user = callback.from_user
        ok, msg = ctx.db.cancel_duel(duel_id, user.id)
        if not ok:
            await callback.answer(msg, show_alert=True)
            return

        await callback.answer("Дуэль отменена.")
        try:
            await callback.message.edit_text(
                f"❌ <b>Дуэль #{duel_id} отменена создателем.</b> Ставка возвращена.",
                parse_mode="HTML",
                reply_markup=None,
            )
        except Exception as e:
            logger.debug("Failed to edit cancel message: %s", e)

    @router.callback_query(F.data.startswith("duel_acc:"))
    async def cb_duel_accept(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        if len(parts) != 2:
            await callback.answer()
            return
        if not await ensure_participant(ctx, callback):
            return

        duel_id = int(parts[1])
        opponent = callback.from_user
        chat_id = callback.message.chat.id

        ctx.db.sync_user(
            chat_id,
            opponent.id,
            opponent.username,
            opponent.first_name,
            opponent.last_name,
        )

        result, err = ctx.db.accept_duel(duel_id, opponent.id)
        if result is None:
            await callback.answer(err, show_alert=True)
            return

        await callback.answer("Вы приняли дуэль! Бросаем кубики...")

        # Delete or edit initial invitation
        try:
            await callback.message.delete()
        except Exception:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

        creator_id = result["creator_id"]
        creator_ident = ctx.db.get_user_identity(chat_id, creator_id) or {}
        creator_name = format_user_name(
            creator_id,
            creator_ident.get("username"),
            creator_ident.get("first_name"),
            creator_ident.get("last_name"),
        )
        opponent_name = format_user_name(
            opponent.id,
            opponent.username,
            opponent.first_name,
            opponent.last_name,
        )

        # Avatars
        creator_av = await fetch_user_avatar(ctx.bot, creator_id)
        opponent_av = await fetch_user_avatar(ctx.bot, opponent.id)

        # Generate Duel Image matching Screenshot 1
        card_buf = render_duel_card(
            creator_avatar=creator_av,
            opponent_avatar=opponent_av,
            creator_name=creator_name,
            opponent_name=opponent_name,
            creator_dice=result["creator_dice"],
            opponent_dice=result["opponent_dice"],
            bet=result["bet"],
        )

        c_sum = result["creator_sum"]
        o_sum = result["opponent_sum"]
        pot = result["pot"]
        bet = result["bet"]
        winner_id = result["winner_id"]

        coin_e = fmt_emoji("coin", "🪙")
        crown_e = fmt_emoji("crown", "👑")
        dice_e = fmt_emoji("dice", "🎲")

        c_dice_str = f"{result['creator_dice'][0]} + {result['creator_dice'][1]} = <b>{c_sum}</b>"
        o_dice_str = f"{result['opponent_dice'][0]} + {result['opponent_dice'][1]} = <b>{o_sum}</b>"

        if winner_id == creator_id:
            outcome_title = f"{crown_e} <b>ПОБЕДА ИНИЦИАТОРА!</b>"
            outcome_desc = (
                f"🏆 <b>{html.escape(creator_name)}</b> одерживает победу и забирает банк <b>{pot:,} {coin_e}</b>!"
            )
        elif winner_id == opponent.id:
            outcome_title = f"{crown_e} <b>ПОБЕДА СОПЕРНИКА!</b>"
            outcome_desc = (
                f"🏆 <b>{html.escape(opponent_name)}</b> одерживает победу и забирает банк <b>{pot:,} {coin_e}</b>!"
            )
        else:
            outcome_title = f"🤝 <b>БОЕВАЯ НИЧЬЯ!</b>"
            outcome_desc = (
                f"Суммы кубиков совпали! Ставки по <b>{bet:,} {coin_e}</b> возвращены обоим бойцам."
            )

        caption = (
            f"{outcome_title}\n"
            f"────────────────────\n"
            f"🔴 <b>{creator_name}:</b> {c_dice_str}\n"
            f"🔵 <b>{opponent_name}:</b> {o_dice_str}\n"
            f"────────────────────\n"
            f"{outcome_desc}"
        ).replace(",", " ")

        photo_file = BufferedInputFile(card_buf.getvalue(), filename=f"duel_{duel_id}.png")
        sent = await callback.message.answer_photo(
            photo=photo_file,
            caption=caption,
            parse_mode="HTML",
        )
        if sent:
            ctx.db.register_message_for_cleanup(
                chat_id,
                sent.chat.id,
                sent.message_id,
                datetime.now().isoformat(),
            )

    return router
