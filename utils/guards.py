from aiogram.enums import ChatType
from aiogram.types import Message


def ensure_group_message(message: Message) -> bool:
    return message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


async def ensure_admin(message: Message) -> bool:
    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in ("administrator", "creator")
