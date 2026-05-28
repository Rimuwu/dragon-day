from datetime import datetime

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from utils.context import AppContext
from utils.guards import ensure_admin, ensure_group_message, ensure_supported_group
from utils.time_utils import parse_range, parse_time_str, sleep_window_for_date, today_str


def _format_state_value(value: str | None, tz, *, date_only: bool = False) -> str:
    if not value:
        return "не назначено"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    if date_only:
        return dt.strftime("%d.%m.%Y")
    return dt.astimezone(tz).strftime("%d.%m.%Y %H:%M:%S")


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

    @router.message(Command("set_points"))
    async def cmd_set_points(message: Message, command: CommandObject) -> None:
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
            await message.answer(
                "Использование: /set_points <day> <evil> <sleepy> или /set_points default для сброса к конфику."
            )
            return
        parts = args.split()
        if len(parts) == 1 and parts[0].lower() in {"default", "defaults", "reset", "config"}:
            ctx.db.set_group_points(
                message.chat.id,
                ctx.config["points_day"],
                ctx.config["points_evil"],
                ctx.config["points_sleepy"],
                ctx.config,
            )
            await message.answer("Очки драконов сброшены на значения из конфига.")
            return
        if len(parts) != 3:
            await message.answer(
                "Использование: /set_points <day> <evil> <sleepy> или /set_points default для сброса к конфику."
            )
            return
        try:
            points_day = int(parts[0])
            points_evil = int(parts[1])
            points_sleepy = int(parts[2])
        except ValueError:
            await message.answer("Очки должны быть целыми числами.")
            return
        ctx.db.set_group_points(message.chat.id, points_day, points_evil, points_sleepy, ctx.config)
        await message.answer(
            "Очки драконов обновлены: "
            f"день {points_day:+d}, злой {points_evil:+d}, сонный {points_sleepy:+d}."
        )

    @router.message(Command("group_settings"))
    async def cmd_group_settings(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        settings = ctx.db.get_group_settings(message.chat.id, ctx.config)
        state = ctx.db.get_group_state(message.chat.id, ctx.config)
        text = (
            "Настройки группы:\n"
            f"• Время ежедневного топа: {settings['daily_time']}\n"
            f"• Окно ночного дракона: {settings['sleep_start']}-{settings['sleep_end']}\n"
            f"• Очки драконов: день {settings['points_day']:+d}, злой {settings['points_evil']:+d}, сонный {settings['points_sleepy']:+d}\n\n"
            "Текущее состояние:\n"
            f"• Последний дракон дня: {_format_state_value(state['last_daily_date'], ctx.tz, date_only=True)}\n"
            f"• Последний злой дракон: {_format_state_value(state['last_evil_date'], ctx.tz, date_only=True)}\n"
            f"• Последний сонный дракон: {_format_state_value(state['last_sleepy_date'], ctx.tz, date_only=True)}\n"
            f"• Следующий сонный: {_format_state_value(state['next_sleepy_at'], ctx.tz)}"
        )
        await message.answer(text)

    return router
