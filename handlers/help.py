from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BotCommand, BotCommandScopeChat, Message

from utils.context import AppContext
from utils.guards import ensure_group_message, ensure_supported_group


def _build_commands() -> list[BotCommand]:
    return [
        BotCommand(command="help", description="Список команд и настройка кнопок"),
        BotCommand(command="add-group", description="Добавить группу (админ бота)"),
        BotCommand(command="enter", description="Вступить в список участников"),
        BotCommand(command="leave", description="Покинуть список участников"),
        BotCommand(command="leaderboard", description="Топы дня/злых/сонных/очков"),
        BotCommand(command="set-time", description="Установить время ежедневного топа"),
        BotCommand(command="sleep-time", description="Установить окно ночного дракона"),
        BotCommand(command="bet-day", description="Ставки на дракона дня"),
        BotCommand(command="bet-evil", description="Ставки на злого дракона"),
        BotCommand(command="cancel-day", description="Отменить ставки на дракона дня"),
        BotCommand(command="cancel-evil", description="Отменить ставки на злого дракона"),
        BotCommand(command="me", description="Профиль игрока"),
    ]


def _build_help_text() -> str:
    return (
        "Команды бота:\n"
        "/add-group — добавить группу (только админ бота)\n"
        "/enter — вступить в список участников\n"
        "/leave — выйти из списка участников\n"
        "/leaderboard [day|evil|sleepy|points] — топ по категориям\n"
        "/set-time HH:MM — время ежедневного топа (админы группы)\n"
        "/sleep-time HH:MM-HH:MM — окно ночного дракона (админы группы)\n"
        "/bet-day — ставки на дракона дня\n"
        "/bet-evil — ставки на злого дракона\n"
        "/cancel-day — отмена ставок на дракона дня\n"
        "/cancel-evil — отмена ставок на злого дракона\n"
        "/me — ваш профиль\n\n"
        "Эта команда также обновляет кнопки команд в группе."
    )


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
        await message.answer(_build_help_text())

    return router