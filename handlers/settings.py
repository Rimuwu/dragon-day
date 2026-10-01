from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

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


def _build_group_settings_message(
    ctx: AppContext, chat_id: int, thread_id: int | None = None
) -> tuple[str, InlineKeyboardMarkup]:
    settings = ctx.db.get_group_settings(chat_id, ctx.config)
    state = ctx.db.get_group_state(chat_id, ctx.config)

    dragons_topic = settings.get("dragons_topic_id")
    commands_topic = settings.get("commands_topic_id")

    d_topic_str = f"#{dragons_topic}" if dragons_topic is not None else "Не задан (общий чат)"
    c_topic_str = f"#{commands_topic}" if commands_topic is not None else "Все топики"

    text = (
        "⚙️ <b>Настройки группы:</b>\n"
        f"• Время топа: <code>{settings['daily_time']}</code>\n"
        f"• Окно ночного дракона: <code>{settings['sleep_start']}-{settings['sleep_end']}</code>\n"
        f"• Очки драконов: день <b>{settings['points_day']:+d}</b>, злой <b>{settings['points_evil']:+d}</b>, сонный <b>{settings['points_sleepy']:+d}</b>\n"
        "────────────────────\n"
        f"🐉 <b>Топик для драконов:</b> <b>{d_topic_str}</b>\n"
        f"🤖 <b>Рабочий топик бота:</b> <b>{c_topic_str}</b>\n"
        "────────────────────\n"
        "📊 <b>Текущее состояние:</b>\n"
        f"• Последний дракон дня: {_format_state_value(state['last_daily_date'], ctx.tz, date_only=True)}\n"
        f"• Последний злой дракон: {_format_state_value(state['last_evil_date'], ctx.tz, date_only=True)}\n"
        f"• Последний сонный дракон: {_format_state_value(state['last_sleepy_date'], ctx.tz, date_only=True)}"
    )

    buttons = []
    if thread_id is not None:
        buttons.append([
            InlineKeyboardButton(text="🐉 Этот топик для драконов", callback_data=f"cfg_set_dragons:{thread_id}"),
            InlineKeyboardButton(text="🤖 Этот топик для бота", callback_data=f"cfg_set_bot:{thread_id}"),
        ])

    reset_row = []
    if dragons_topic is not None:
        reset_row.append(InlineKeyboardButton(text="🔄 Сбросить драконов", callback_data="cfg_reset_dragons"))
    if commands_topic is not None:
        reset_row.append(InlineKeyboardButton(text="🔄 Сбросить топик бота", callback_data="cfg_reset_bot"))
    if reset_row:
        buttons.append(reset_row)

    if dragons_topic is not None and commands_topic is not None:
        buttons.append([InlineKeyboardButton(text="❌ Сбросить оба топика", callback_data="cfg_reset_both")])

    buttons.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="cfg_refresh")])
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


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

    @router.message(Command("set_dragon_topic", "dragon_topic", "dragons_topic"))
    async def cmd_set_dragon_topic(message: Message, command: CommandObject) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        if not await ensure_admin(message):
            await message.answer("Команда доступна только администраторам.")
            return

        args = (command.args or "").strip().lower()
        if args in ("reset", "clear", "none", "off", "0", "default"):
            ctx.db.set_group_dragons_topic(message.chat.id, None, ctx.config)
            await message.answer("🔄 Топик для драконов сброшен! Теперь дракон дня, ночной и злой драконы будут отправляться в общий чат.")
            return

        if args.isdigit():
            topic_id = int(args)
            ctx.db.set_group_dragons_topic(message.chat.id, topic_id, ctx.config)
            await message.answer(f"🐉 Топик для драконов (день, зло, ночь) установлен: <b>#{topic_id}</b>.")
            return

        thread_id = message.message_thread_id
        if thread_id is not None:
            ctx.db.set_group_dragons_topic(message.chat.id, thread_id, ctx.config)
            await message.answer(f"🐉 Топик для драконов (день, зло, ночь) установлен на текущий топик: <b>#{thread_id}</b>.")
            return

        await message.answer(
            "⚠️ Вы находитесь не в топике.\n\n"
            "• Напишите <code>/set_dragon_topic</code> внутри нужного топика\n"
            "• Или укажите ID топика: <code>/set_dragon_topic &lt;ID&gt;</code>\n"
            "• Для сброса: <code>/set_dragon_topic reset</code>"
        )

    @router.message(Command("set_bot_topic", "bot_topic"))
    async def cmd_set_bot_topic(message: Message, command: CommandObject) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        if not await ensure_admin(message):
            await message.answer("Команда доступна только администраторам.")
            return

        args = (command.args or "").strip().lower()
        if args in ("reset", "clear", "none", "off", "0", "default"):
            ctx.db.set_group_commands_topic(message.chat.id, None, ctx.config)
            await message.answer("🔄 Ограничение по топику сброшено! Теперь бот реагирует на команды во всех топиках группы.")
            return

        if args.isdigit():
            topic_id = int(args)
            ctx.db.set_group_commands_topic(message.chat.id, topic_id, ctx.config)
            await message.answer(f"🤖 Рабочий топик бота установлен: <b>#{topic_id}</b>. В остальных топиках бот не будет реагировать на команды.")
            return

        thread_id = message.message_thread_id
        if thread_id is not None:
            ctx.db.set_group_commands_topic(message.chat.id, thread_id, ctx.config)
            await message.answer(f"🤖 Рабочий топик бота установлен на текущий топик: <b>#{thread_id}</b>. В остальных топиках бот не будет реагировать на команды.")
            return

        await message.answer(
            "⚠️ Вы находитесь не в топике.\n\n"
            "• Напишите <code>/set_bot_topic</code> внутри нужного топика\n"
            "• Или укажите ID топика: <code>/set_bot_topic &lt;ID&gt;</code>\n"
            "• Для сброса: <code>/set_bot_topic reset</code>"
        )

    @router.message(Command("group_settings", "settings"))
    async def cmd_group_settings(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        thread_id = message.message_thread_id
        text, kb = _build_group_settings_message(ctx, message.chat.id, thread_id)
        await message.answer(text, parse_mode="HTML", reply_markup=kb)

    @router.callback_query(F.data.startswith("cfg_"))
    async def cb_group_settings(callback: CallbackQuery) -> None:
        if callback.message is None:
            await callback.answer()
            return
        if not await ensure_supported_group(ctx, callback):
            return

        member = await callback.bot.get_chat_member(callback.message.chat.id, callback.from_user.id)
        if member.status not in ("administrator", "creator"):
            await callback.answer("Настройки доступны только администраторам.", show_alert=True)
            return

        chat_id = callback.message.chat.id
        thread_id = callback.message.message_thread_id
        action = callback.data

        if action.startswith("cfg_set_dragons:"):
            t_id = int(action.split(":")[1])
            ctx.db.set_group_dragons_topic(chat_id, t_id, ctx.config)
            await callback.answer(f"Топик для драконов установлен на #{t_id}!", show_alert=True)
        elif action.startswith("cfg_set_bot:"):
            t_id = int(action.split(":")[1])
            ctx.db.set_group_commands_topic(chat_id, t_id, ctx.config)
            await callback.answer(f"Рабочий топик бота установлен на #{t_id}!", show_alert=True)
        elif action == "cfg_reset_dragons":
            ctx.db.set_group_dragons_topic(chat_id, None, ctx.config)
            await callback.answer("Топик для драконов сброшен!", show_alert=True)
        elif action == "cfg_reset_bot":
            ctx.db.set_group_commands_topic(chat_id, None, ctx.config)
            await callback.answer("Рабочий топик бота сброшен!", show_alert=True)
        elif action == "cfg_reset_both":
            ctx.db.reset_group_topics(chat_id, ctx.config)
            await callback.answer("Оба топика сброшены!", show_alert=True)
        elif action == "cfg_refresh":
            await callback.answer("Обновлено")

        text, kb = _build_group_settings_message(ctx, chat_id, thread_id)
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            pass

    return router

