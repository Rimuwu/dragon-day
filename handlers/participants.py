from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from utils.context import AppContext
from utils.guards import ensure_group_message, ensure_supported_group


def get_router(ctx: AppContext) -> Router:
    router = Router()

    @router.message(Command("enter"))
    async def cmd_enter(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Участвовать", callback_data=f"join:{message.chat.id}")]
            ]
        )
        await message.answer("Нажмите кнопку, чтобы вступить в список участников.", reply_markup=keyboard)

    @router.callback_query(F.data.startswith("join:"))
    async def cb_join(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        if callback.message is None or callback.message.chat.id != group_id:
            await callback.answer("Ошибка группы.")
            return
        if not await ensure_supported_group(ctx, callback):
            return
        user = callback.from_user
        if ctx.db.is_participant(group_id, user.id):
            await callback.answer("Вы уже зарегистрированы.")
            return
        ctx.db.add_participant(
            group_id,
            user.id,
            user.username,
            user.first_name,
            user.last_name,
            datetime.now(ctx.tz).isoformat(),
        )
        await callback.answer("Вы добавлены в список участников.")

    @router.message(Command("leave"))
    async def cmd_leave(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Да",
                        callback_data=f"leave:{message.chat.id}:{message.from_user.id}:yes",
                    ),
                    InlineKeyboardButton(
                        text="Нет",
                        callback_data=f"leave:{message.chat.id}:{message.from_user.id}:no",
                    ),
                ]
            ]
        )
        await message.answer("Удалить вас из списка участников?", reply_markup=keyboard)

    @router.callback_query(F.data.startswith("leave:"))
    async def cb_leave(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        user_id = int(parts[2])
        action = parts[3]
        if callback.from_user.id != user_id:
            await callback.answer("Это не ваша кнопка.")
            return
        if callback.message is None or callback.message.chat.id != group_id:
            await callback.answer("Ошибка группы.")
            return
        if not await ensure_supported_group(ctx, callback):
            return
        if action == "no":
            await callback.message.delete()
            return
        ctx.db.remove_participant(group_id, user_id)
        await callback.message.delete()
        await callback.answer("Вы удалены из списка участников.")

    return router
