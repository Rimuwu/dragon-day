from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.context import AppContext
from utils.guards import ensure_group_message, ensure_supported_group


def get_router(ctx: AppContext) -> Router:
    router = Router()

    @router.message(Command("add_group"))
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

    @router.message(Command("points"))
    async def cmd_points(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        if message.from_user.id != ctx.admin_id:
            await message.answer("Команда доступна только администратору бота.")
            return
        args = (message.text or "").split()
        if len(args) < 2:
            await message.answer("Использование: /points <delta> (ответом на сообщение) или /points <user_id> <delta>.")
            return
        if message.reply_to_message and len(args) == 2:
            target_id = message.reply_to_message.from_user.id
            delta_raw = args[1]
        elif len(args) >= 3:
            target_id = int(args[1])
            delta_raw = args[2]
        else:
            await message.answer("Укажите пользователя и изменение очков.")
            return
        try:
            delta = int(delta_raw)
        except ValueError:
            await message.answer("Неверное значение очков.")
            return
        ctx.db.adjust_points(message.chat.id, target_id, delta)
        await message.answer(f"Очки обновлены: {target_id} ({delta:+d}).")

    return router