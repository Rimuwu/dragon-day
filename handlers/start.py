from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from utils.context import AppContext
from utils.guards import ensure_admin, ensure_group_message, ensure_supported_group
from utils.time_utils import parse_range, parse_time_str



def get_router(ctx: AppContext) -> Router:
    router = Router()

    @router.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        await message.answer("Раррр!")
        
    return router