from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from utils.context import AppContext
from utils.guards import ensure_group_message, ensure_supported_group
from utils.keyboards import build_leaderboard_keyboard
from utils.texts import build_leaderboard_text

PAGE_SIZE = 10


def get_router(ctx: AppContext) -> Router:
    router = Router()

    async def send_leaderboard(
        target: Message | CallbackQuery,
        group_id: int,
        owner_id: int,
        kind: str,
        page: int,
    ) -> None:
        total = ctx.db.count_stats(group_id)
        offset = page * PAGE_SIZE
        entries = ctx.db.get_leaderboard(group_id, kind, PAGE_SIZE, offset)
        text = build_leaderboard_text(kind, entries, page, total, PAGE_SIZE)
        keyboard = build_leaderboard_keyboard(group_id, owner_id, kind, page, total, PAGE_SIZE)
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text, reply_markup=keyboard)
            ctx.db.register_message_for_cleanup(
                group_id,
                target.message.chat.id,
                target.message.message_id,
                datetime.now().isoformat(),
            )
        else:
            sent = await target.answer(text, reply_markup=keyboard)
            ctx.db.register_message_for_cleanup(
                group_id,
                sent.chat.id,
                sent.message_id,
                datetime.now().isoformat(),
            )

    @router.message(Command("leaderboard"))
    async def cmd_leaderboard(message: Message, command: CommandObject) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        args = (command.args or "").strip().lower()
        kind = args if args in {"day", "evil", "sleepy", "points"} else "points"
        await send_leaderboard(message, message.chat.id, message.from_user.id, kind, 0)

    @router.callback_query(F.data.startswith("lb:"))
    async def cb_leaderboard(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        owner_id = int(parts[2])
        kind = parts[3]
        page = int(parts[4])
        if callback.from_user.id != owner_id:
            await callback.answer("Эти кнопки только для автора.")
            return
        if callback.message is None or callback.message.chat.id != group_id:
            await callback.answer("Ошибка группы.")
            return
        if not await ensure_supported_group(ctx, callback):
            return
        await send_leaderboard(callback, group_id, owner_id, kind, page)
        await callback.answer()

    return router
