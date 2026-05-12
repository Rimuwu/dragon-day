from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message

from utils.context import AppContext


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
