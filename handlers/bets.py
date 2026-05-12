from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from utils.context import AppContext
from utils.guards import ensure_group_message, ensure_supported_group
from utils.keyboards import build_bet_keyboard
from utils.texts import bet_title, build_bet_text
from utils.time_utils import today_str

PAGE_SIZE = 10


def get_router(ctx: AppContext) -> Router:
    router = Router()

    async def send_bet_menu(
        target: Message | CallbackQuery,
        group_id: int,
        owner_id: int,
        bet_type: str,
        page: int,
    ) -> None:
        participants = ctx.db.list_participants(group_id)
        total = len(participants)
        if total == 0:
            text = f"Ставка на {bet_title(bet_type)}\n\nПока нет участников."
            if isinstance(target, CallbackQuery):
                await target.message.edit_text(text)
            else:
                await target.answer(text)
            return

        bet_date = today_str(ctx.tz)
        amounts = ctx.db.get_bet_amounts(group_id, owner_id, bet_type, bet_date)
        points = ctx.db.get_points(group_id, owner_id)
        offset = page * PAGE_SIZE
        page_items = participants[offset : offset + PAGE_SIZE]
        text = build_bet_text(bet_type, points, page_items, amounts, page, total, PAGE_SIZE, ctx.config["bet_step"])
        keyboard = build_bet_keyboard(
            group_id,
            owner_id,
            bet_type,
            page_items,
            page,
            total,
            PAGE_SIZE,
            ctx.config["bet_step"],
        )
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text, reply_markup=keyboard)
        else:
            await target.answer(text, reply_markup=keyboard)

    @router.message(Command("bet-day"))
    async def cmd_bet_day(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        ctx.db.upsert_user(
            message.chat.id,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        await send_bet_menu(message, message.chat.id, message.from_user.id, "day", 0)

    @router.message(Command("bet-evil"))
    async def cmd_bet_evil(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        ctx.db.upsert_user(
            message.chat.id,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        await send_bet_menu(message, message.chat.id, message.from_user.id, "evil", 0)

    @router.callback_query(F.data.startswith("betpage:"))
    async def cb_bet_page(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        owner_id = int(parts[2])
        bet_type = parts[3]
        page = int(parts[4])
        if callback.from_user.id != owner_id:
            await callback.answer("Эти кнопки только для автора.")
            return
        if callback.message is None or callback.message.chat.id != group_id:
            await callback.answer("Ошибка группы.")
            return
        if not await ensure_supported_group(ctx, callback):
            return
        await send_bet_menu(callback, group_id, owner_id, bet_type, page)
        await callback.answer()

    @router.callback_query(F.data.startswith("bet:"))
    async def cb_bet_adjust(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        owner_id = int(parts[2])
        bet_type = parts[3]
        target_id = int(parts[4])
        delta = int(parts[5])
        page = int(parts[6])
        if callback.from_user.id != owner_id:
            await callback.answer("Эти кнопки только для автора.")
            return
        if callback.message is None or callback.message.chat.id != group_id:
            await callback.answer("Ошибка группы.")
            return
        if not await ensure_supported_group(ctx, callback):
            return
        ctx.db.upsert_user(
            group_id,
            owner_id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name,
        )
        ok, error = ctx.db.adjust_bet(group_id, owner_id, bet_type, target_id, today_str(ctx.tz), delta)
        if not ok:
            await callback.answer(error, show_alert=True)
            return
        await send_bet_menu(callback, group_id, owner_id, bet_type, page)
        await callback.answer()

    @router.message(Command("cancel-day"))
    async def cmd_cancel_day(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        refunded = ctx.db.cancel_bets(message.chat.id, message.from_user.id, "day", today_str(ctx.tz))
        await message.answer(f"Ставки отменены, возвращено очков: {refunded}.")

    @router.message(Command("cancel-evil"))
    async def cmd_cancel_evil(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        refunded = ctx.db.cancel_bets(message.chat.id, message.from_user.id, "evil", today_str(ctx.tz))
        await message.answer(f"Ставки отменены, возвращено очков: {refunded}.")

    return router
