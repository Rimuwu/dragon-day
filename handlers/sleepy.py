from datetime import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery

from utils.context import AppContext
from utils.guards import ensure_supported_group


def get_router(ctx: AppContext) -> Router:
    router = Router()

    @router.callback_query(F.data.startswith("sleepjoin:"))
    async def cb_sleep_join(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        sleep_date = parts[2]
        if callback.message is None or callback.message.chat.id != group_id:
            await callback.answer("Ошибка группы.")
            return
        if not await ensure_supported_group(ctx, callback):
            return
        event = ctx.db.get_sleep_event(group_id, sleep_date)
        if not event:
            await callback.answer("Событие уже закрыто.")
            return
        closes_at = datetime.fromisoformat(event["closes_at"])
        if datetime.now(ctx.tz) > closes_at:
            await callback.answer("Поздно, набор закрыт.")
            return
        user = callback.from_user
        ctx.db.upsert_user(group_id, user.id, user.username, user.first_name, user.last_name)
        ctx.db.add_sleep_entry(group_id, user.id, sleep_date)
        await callback.answer("Вы участвуете в ночном драконе.")

    return router
