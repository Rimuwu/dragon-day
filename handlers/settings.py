from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from utils.context import AppContext
from utils.guards import ensure_admin, ensure_group_message, ensure_supported_group
from utils.time_utils import parse_range, parse_time_str


def get_router(ctx: AppContext) -> Router:
    router = Router()

    @router.message(Command("set-time"))
    async def cmd_set_time(message: Message, command: CommandObject) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        if not await ensure_admin(message):
            await message.answer("Команда доступна только администраторам.")
            return
        args = (command.args or "").strip()
        if not args:
            await message.answer("Укажите время в формате HH:MM, например /set-time 10:00.")
            return
        try:
            parse_time_str(args)
        except ValueError:
            await message.answer("Неверный формат времени. Используйте HH:MM.")
            return
        ctx.db.set_group_time(message.chat.id, args, ctx.config)
        await message.answer(f"Время ежедневного топа установлено на {args} (МСК).")

    @router.message(Command("sleep-time"))
    async def cmd_sleep_time(message: Message, command: CommandObject) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        if not await ensure_admin(message):
            await message.answer("Команда доступна только администраторам.")
            return
        args = (command.args or "").strip()
        if not args:
            await message.answer("Укажите диапазон HH:MM-HH:MM, например /sleep-time 23:00-02:00.")
            return
        try:
            start_time, end_time = parse_range(args)
        except ValueError:
            await message.answer("Неверный формат. Используйте HH:MM-HH:MM.")
            return
        ctx.db.set_group_sleep_range(
            message.chat.id,
            start_time.strftime("%H:%M"),
            end_time.strftime("%H:%M"),
            ctx.config,
        )
        await message.answer(
            f"Диапазон ночного дракона установлен: {start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')} (МСК)."
        )

    return router
