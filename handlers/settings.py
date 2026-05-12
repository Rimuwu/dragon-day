from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from utils.context import AppContext
from utils.guards import ensure_admin, ensure_group_message, ensure_supported_group
from utils.time_utils import parse_range, parse_time_str, sleep_window_for_date, today_str


def get_router(ctx: AppContext) -> Router:
    router = Router()

    @router.message(Command("set_time"))
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
            await message.answer("Укажите время в формате HH:MM, например /set_time 10:00.")
            return
        try:
            parse_time_str(args)
        except ValueError:
            await message.answer("Неверный формат времени. Используйте HH:MM.")
            return
        ctx.db.set_group_time(message.chat.id, args, ctx.config)
        await message.answer(f"Время ежедневного топа установлено на {args} (МСК).")

    @router.message(Command("sleep_time"))
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
            await message.answer("Укажите диапазон HH:MM-HH:MM, например /sleep_time 23:00-02:00.")
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
        state = ctx.db.get_group_state(message.chat.id, ctx.config)
        now = message.date.astimezone(ctx.tz)
        today = today_str(ctx.tz)
        next_sleepy_at = None
        if state["last_sleepy_date"] != today:
            start_dt, end_dt = sleep_window_for_date(now, start_time, end_time, ctx.tz)
            if start_dt <= now <= end_dt:
                next_sleepy_at = now
        ctx.db.set_group_state(
            message.chat.id,
            state["last_daily_date"],
            state["last_evil_date"],
            state["last_sleepy_date"],
            next_sleepy_at.isoformat() if next_sleepy_at else None,
            ctx.config,
        )
        await message.answer(
            f"Диапазон ночного дракона установлен: {start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')} (МСК)."
        )

    return router
