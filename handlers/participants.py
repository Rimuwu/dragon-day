from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from utils.context import AppContext
from utils.guards import ensure_group_message, ensure_supported_group
from utils.helpers import format_user_name


def get_router(ctx: AppContext) -> Router:
    router = Router()

    @router.message(Command("enter"))
    async def cmd_enter(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        if not message.from_user:
            return

        user = message.from_user
        name = format_user_name(user.id, user.username, user.first_name, user.last_name)

        if ctx.db.is_participant(message.chat.id, user.id):
            ctx.db.sync_user(
                message.chat.id,
                user.id,
                user.username,
                user.first_name,
                user.last_name,
            )
            await message.answer(
                f"✅ <b>{name}</b>, вы уже состоите в списке участников и играете!",
                parse_mode="HTML",
            )
            return

        ctx.db.add_participant(
            message.chat.id,
            user.id,
            user.username,
            user.first_name,
            user.last_name,
            datetime.now(ctx.tz).isoformat(),
        )
        welcome_text = (
            f"🎉 <b>{name}, добро пожаловать в игру «Дракон Дня»!</b>\n\n"
            f"Вы успешно вступили в список участников. Вам начислено <b>100 🪙</b> стартовых очков!\n\n"
            f"Теперь вам доступны:\n"
            f"• 👤 /me — ваш профиль и статистика\n"
            f"• 🎲 /roll — ежедневный бросок кубика\n"
            f"• ⚔️ /duel &lt;ставка&gt; — дуэль на кубиках\n"
            f"• 🎟️ /lottery &lt;ставка&gt; — королевская лотерея\n"
            f"• 🐲 /bet_day и /bet_evil — ставки на драконов дня\n"
            f"• 🏆 /leaderboard — таблица лидеров"
        )
        sent = await message.answer(welcome_text, parse_mode="HTML")
        if sent:
            ctx.db.register_message_for_cleanup(
                message.chat.id,
                sent.chat.id,
                sent.message_id,
                datetime.now().isoformat(),
            )

    @router.callback_query(F.data.startswith("join:"))
    async def cb_join(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        if callback.message is None or callback.message.chat.id != group_id:
            await callback.answer("Ошибка группы.", show_alert=True)
            return
        if not await ensure_supported_group(ctx, callback):
            return
        user = callback.from_user
        if not user:
            return

        name = format_user_name(user.id, user.username, user.first_name, user.last_name)
        if ctx.db.is_participant(group_id, user.id):
            ctx.db.sync_user(group_id, user.id, user.username, user.first_name, user.last_name)
            await callback.answer("✅ Вы уже состоите в списке участников!", show_alert=False)
            return

        ctx.db.add_participant(
            group_id,
            user.id,
            user.username,
            user.first_name,
            user.last_name,
            datetime.now(ctx.tz).isoformat(),
        )
        await callback.answer("🎉 Вы успешно вступили в игру! Вам начислено 100 🪙", show_alert=True)

        welcome_text = (
            f"🎉 <b>{name}, добро пожаловать в игру «Дракон Дня»!</b>\n\n"
            f"Вы успешно вступили в список участников. Вам начислено <b>100 🪙</b> стартовых очков!\n\n"
            f"Теперь вам доступны:\n"
            f"• 👤 /me — ваш профиль и статистика\n"
            f"• 🎲 /roll — ежедневный бросок кубика\n"
            f"• ⚔️ /duel &lt;ставка&gt; — дуэль на кубиках\n"
            f"• 🎟️ /lottery &lt;ставка&gt; — королевская лотерея\n"
            f"• 🐲 /bet_day и /bet_evil — ставки на драконов дня\n"
            f"• 🏆 /leaderboard — таблица лидеров"
        )
        try:
            await callback.message.edit_text(welcome_text, parse_mode="HTML", reply_markup=None)
        except Exception:
            sent = await callback.message.answer(welcome_text, parse_mode="HTML")
            if sent:
                ctx.db.register_message_for_cleanup(
                    group_id,
                    sent.chat.id,
                    sent.message_id,
                    datetime.now().isoformat(),
                )

    @router.message(Command("leave"))
    async def cmd_leave(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        if not message.from_user:
            return
        if not ctx.db.is_participant(message.chat.id, message.from_user.id):
            await message.answer("Вы и так не состоите в списке участников.")
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
