from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.context import AppContext
from utils.guards import ensure_group_message, ensure_supported_group
from utils.time_utils import today_str


def get_router(ctx: AppContext) -> Router:
    router = Router()

    @router.message(Command("me"))
    async def cmd_me(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        ctx.db.sync_user(
            message.chat.id,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        stats = ctx.db.get_user_stats(message.chat.id, message.from_user.id)
        if not stats:
            await message.answer("Профиль пуст. Участвуйте в событиях, чтобы появились данные.")
            return
        bets_played = stats["bets_played"]
        bets_won = stats["bets_won"]
        bets_lost = bets_played - bets_won
        open_bets = ctx.db.count_open_bets(message.chat.id, message.from_user.id, today_str(ctx.tz))
        text = (
            f"Профиль\n"
            f"Очки: {stats['points']}\n"
            f"Победы (день/злой/сонный): {stats['wins_day']} / {stats['wins_evil']} / {stats['wins_sleepy']}\n"
            f"Сыгранные ставки: {bets_played}\n"
            f"Не сыгравшие ставки: {bets_lost}\n"
            f"Открытые ставки сегодня: {open_bets}"
        )
        await message.answer(text)

    return router
