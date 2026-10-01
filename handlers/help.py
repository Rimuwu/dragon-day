from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BotCommand, BotCommandScopeChat, Message

from utils.context import AppContext
from utils.guards import ensure_group_message, ensure_supported_group


def _build_commands() -> list[BotCommand]:
    return [
        BotCommand(command="help", description="Справочник команд бота"),
        BotCommand(command="me", description="Ваш профиль и статистика"),
        BotCommand(command="enter", description="Вступить в стаю"),
        BotCommand(command="leave", description="Покинуть игру"),
        BotCommand(command="leaderboard", description="Зал славы и топы"),
        BotCommand(command="roll", description="Ежедневный кубик 🎲 (1 раз в день)"),
        BotCommand(command="basket", description="Баскетбол 🏀 (1 раз в день)"),
        BotCommand(command="bowling", description="Боулинг 🎳 (1 раз в день)"),
        BotCommand(command="football", description="Футбол ⚽ (1 раз в день)"),
        BotCommand(command="duel", description="Дуэль на кубиках (/duel <ставка>)"),
        BotCommand(command="lottery", description="Лотерея (/lottery <ставка> или /lottery <номер>)"),
        BotCommand(command="bet_day", description="Ставки на дракона дня"),
        BotCommand(command="bet_evil", description="Ставки на злого дракона"),
        BotCommand(command="my_bets", description="Мои активные ставки"),
        BotCommand(command="cancel_day", description="Снять ставку на дракона дня"),
        BotCommand(command="cancel_evil", description="Снять ставку на злого дракона"),
        BotCommand(command="group_settings", description="Настройки группы"),
        BotCommand(command="set_time", description="Время топа (админ группы)"),
        BotCommand(command="sleep_time", description="Окно сна (админ группы)"),
        BotCommand(command="set_points", description="Очки драконов (админ группы)"),
    ]


def _build_help_text(is_bot_admin: bool = False) -> str:
    lines = [
        "📖 <b>СПРАВОЧНИК КОМАНД • DRAGON DAY</b>",
        "────────────────────",
        "",
        "👤 <b>Участие и профиль:</b>",
        "• <code>/enter</code> — вступить в стаю и участвовать в событиях",
        "• <code>/leave</code> — выйти из игры",
        "• <code>/me</code> — профиль, винрейт, серии побед, шансы и очки",
        "",
        "🏆 <b>Рейтинги и зал славы:</b>",
        "• <code>/leaderboard</code> (или <code>/top</code>) — общий зал славы и топы",
        "",
        "🎲 <b>Мини-игры и заработок:</b>",
        "• <code>/roll</code> — бросок кубика раз в сутки 🎲",
        "• <code>/basket</code> — баскетбол в кольцо раз в сутки 🏀",
        "• <code>/bowling</code> — боулинг со страйками раз в сутки 🎳",
        "• <code>/football</code> — пенальти в футболе раз в сутки ⚽",
        "• <code>/duel &lt;ставка&gt;</code> — дуэль на кубиках 2d6 (ответом или открытая)",
        "• <code>/lottery &lt;ставка&gt; [номер]</code> — запустить лотерею на 100 билетов (банк = сумма ставок)",
        "• <code>/lottery &lt;номер&gt;</code> — купить выбранный билет (1–100) в активной лотерее",
        "",
        "🔥 <b>Ставки на драконов:</b>",
        "• <code>/bet_day</code> — открыть пул ставок на Дракона Дня",
        "• <code>/bet_evil</code> — открыть пул ставок на Злого Дракона",
        "• <code>/my_bets</code> — просмотр активных ставок на сегодня",
        "• <code>/cancel_day</code> — отменить ставку на дракона дня",
        "• <code>/cancel_evil</code> — отменить ставку на злого дракона",
        "",
        "⚙️ <b>Настройки группы (для админов):</b>",
        "• <code>/group_settings</code> — текущие параметры и расписание",
        "• <code>/set_time HH:MM</code> — время выбора дракона дня",
        "• <code>/sleep_time HH:MM-HH:MM</code> — окно сна ночного дракона",
        "• <code>/set_points &lt;день&gt; &lt;злой&gt; &lt;сонный&gt;</code> — награды в очках",
    ]

    if is_bot_admin:
        lines.extend([
            "",
            "🛠 <b>Управление ботом (админ бота):</b>",
            "• <code>/add_group</code> — привязать группу к боту",
            "• <code>/repick &lt;day|evil&gt;</code> — переиграть результат",
            "• <code>/points &lt;@user&gt; &lt;очки&gt;</code> — начислить/списать очки",
        ])

    lines.extend([
        "────────────────────",
        "<i>💡 Меню команд бота в Telegram также автоматически обновлено!</i>",
    ])
    return "\n".join(lines)


def get_router(ctx: AppContext) -> Router:
    router = Router()

    @router.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        await message.bot.set_my_commands(
            _build_commands(),
            scope=BotCommandScopeChat(chat_id=message.chat.id),
        )
        is_bot_admin = message.from_user is not None and message.from_user.id == ctx.admin_id
        sent = await message.answer(_build_help_text(is_bot_admin), parse_mode="HTML")
        ctx.db.register_message_for_cleanup(
            message.chat.id,
            sent.chat.id,
            sent.message_id,
            datetime.now().isoformat(),
        )

    return router