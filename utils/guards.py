from datetime import datetime
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
)

from utils.context import AppContext
from utils.helpers import format_user_name


def ensure_group_message(message: Message) -> bool:
    return message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


async def ensure_admin(message: Message) -> bool:
    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in ("administrator", "creator")


async def ensure_supported_group(ctx: AppContext, target: Message | CallbackQuery) -> bool:
    chat = target.message.chat if isinstance(target, CallbackQuery) else target.chat
    if not ctx.db.is_group_allowed(chat.id):
        text = "Группа не поддерживается. Попросите администратора бота добавить /add_group."
        if isinstance(target, CallbackQuery):
            await target.answer(text, show_alert=True)
        else:
            await target.answer(text)
        return False
    return True


async def ensure_participant(ctx: AppContext, target: Message | CallbackQuery) -> bool:
    if isinstance(target, CallbackQuery):
        chat = target.message.chat if target.message else None
    else:
        chat = getattr(target, "chat", None)

    if not chat:
        return False

    user = target.from_user
    if not user:
        return False

    if ctx.db.is_participant(chat.id, user.id):
        return True

    if isinstance(target, CallbackQuery):
        await target.answer(
            "⚠️ Вы ещё не вступили в игру! Вступите через команду /enter",
            show_alert=True,
        )
        return False

    name = format_user_name(user.id, user.username, user.first_name, user.last_name)
    text = (
        f"⚠️ <b>{name}, вы ещё не вступили в игру!</b>\n\n"
        f"Чтобы играть, смотреть профиль, бросать кубик, участвовать в дуэлях, лотереях и делать ставки, "
        f"необходимо вступить в игру.\n\n"
        f"Нажмите кнопку ниже или отправьте команду <b>/enter</b>:"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🐲 Вступить в игру",
                    callback_data=f"join:{chat.id}",
                )
            ]
        ]
    )
    sent = await target.answer(text, parse_mode="HTML", reply_markup=keyboard)
    if sent:
        ctx.db.register_message_for_cleanup(
            chat.id,
            sent.chat.id,
            sent.message_id,
            datetime.now().isoformat(),
        )
    return False


class TopicCommandsMiddleware(BaseMiddleware):
    def __init__(self, ctx: AppContext):
        self.ctx = ctx

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            if event.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
                text = (event.text or event.caption or "").strip()
                if text.startswith("/"):
                    cmd = text.split()[0].split("@")[0].lower()
                    admin_bypass_cmds = {
                        "/set_bot_topic",
                        "/bot_topic",
                        "/set_dragon_topic",
                        "/dragon_topic",
                        "/dragons_topic",
                        "/group_settings",
                        "/settings",
                        "/set_time",
                        "/sleep_time",
                        "/set_points",
                        "/add_group",
                        "/repick",
                        "/points",
                    }
                    if cmd in admin_bypass_cmds:
                        return await handler(event, data)

                    settings = self.ctx.db.get_group_settings(event.chat.id, self.ctx.config)
                    commands_topic = settings.get("commands_topic_id")
                    if commands_topic is not None:
                        msg_thread = event.message_thread_id
                        if msg_thread != commands_topic:
                            return None

        elif isinstance(event, CallbackQuery):
            if event.message and event.message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
                cb_data = event.data or ""
                if cb_data.startswith(("cfg_", "join:", "sleepjoin:")):
                    return await handler(event, data)

                settings = self.ctx.db.get_group_settings(event.message.chat.id, self.ctx.config)
                commands_topic = settings.get("commands_topic_id")
                if commands_topic is not None:
                    msg_thread = event.message.message_thread_id
                    if msg_thread != commands_topic:
                        await event.answer()
                        return None

        return await handler(event, data)

