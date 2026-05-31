import asyncio

from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.context import AppContext
from utils.guards import ensure_group_message, ensure_supported_group
from utils.time_utils import today_str


def get_router(ctx: AppContext) -> Router:
    router = Router()

    @router.message(Command("roll"))
    async def cmd_roll(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        
        today = today_str(ctx.tz)
        if ctx.db.check_roll_used(message.chat.id, message.from_user.id, today):
            await message.answer("Вы уже использовали /roll сегодня. Приходите завтра!")
            return
        
        dice_msg = await message.answer_dice(emoji="🎲")
        
        dice_value = dice_msg.dice.value
        points = ctx.config["dice_points"].get(str(dice_value), 0)
        
        ctx.db.adjust_points(message.chat.id, message.from_user.id, points)
        ctx.db.record_roll(message.chat.id, message.from_user.id, today)

        await asyncio.sleep(5)
        
        await message.answer(f"🎲 Вы получаете {points} очков! (выпало {dice_value})")

    return router
