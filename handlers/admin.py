from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.context import AppContext
from utils.guards import ensure_group_message


def get_router(ctx: AppContext) -> Router:
    router = Router()

    @router.message(Command("add-group"))
    async def cmd_add_group(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if message.from_user.id != ctx.admin_id:
            await message.answer("Команда доступна только администратору бота.")
            return
        added = ctx.db.allow_group(
            message.chat.id,
            message.from_user.id,
            datetime.now(ctx.tz).isoformat(),
            ctx.config,
        )
        if added:
            await message.answer("Группа добавлена и готова к работе.")
        else:
            await message.answer("Группа уже добавлена.")

    return router