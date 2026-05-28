import asyncio
from datetime import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from utils.context import AppContext
from utils.guards import ensure_group_message, ensure_supported_group
from utils.helpers import format_user_name
from utils.texts import bet_title
from utils.time_utils import today_str

PAGE_SIZE = 10


async def safe_edit_message(message, text, reply_markup=None, retries: int = 1):
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        msg = str(e)
        if "message is not modified" in msg:
            return
        raise
    except TelegramRetryAfter as e:
        wait = getattr(e, "retry_after", 1)
        if retries > 0:
            await asyncio.sleep(wait)
            return await safe_edit_message(message, text, reply_markup=reply_markup, retries=retries - 1)
        raise


def get_router(ctx: AppContext) -> Router:
    router = Router()

    async def send_bet_menu(
        target: Message | CallbackQuery,
        group_id: int,
        owner_id: int,
        bet_type: str,
        page: int,
    ) -> None:
        participants = ctx.db.list_participants(group_id)
        total = len(participants)
        if total == 0:
            text = f"Ставка на {bet_title(bet_type)}\n\nПока нет участников."
            if isinstance(target, CallbackQuery):
                await safe_edit_message(target.message, text)
                ctx.db.register_message_for_cleanup(
                    group_id,
                    target.message.chat.id,
                    target.message.message_id,
                    datetime.now().isoformat(),
                )
            else:
                sent = await target.answer(text)
                ctx.db.register_message_for_cleanup(
                    group_id,
                    sent.chat.id,
                    sent.message_id,
                    datetime.now().isoformat(),
                )
            return

        offset = page * PAGE_SIZE
        page_items = participants[offset : offset + PAGE_SIZE]
        lines = [
            f"Ставка на {bet_title(bet_type)}",
            "",
            "Выберите игрока:",
        ]
        start_index = page * PAGE_SIZE + 1
        for idx, person in enumerate(page_items, start=start_index):
            name = format_user_name(
                person["user_id"],
                None,
                person.get("first_name"),
                person.get("last_name"),
            )
            lines.append(f"{idx}. {name}")
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        lines.append("")
        lines.append(f"Страница {page + 1} / {total_pages}")
        text = "\n".join(lines)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        row: list[InlineKeyboardButton] = []
        for person in page_items:
            name = format_user_name(
                person["user_id"],
                None,
                person.get("first_name"),
                person.get("last_name"),
            )
            row.append(
                InlineKeyboardButton(
                    text=f"{name} ({person['username']})",
                    callback_data=f"betpick:{group_id}:{owner_id}:{bet_type}:{person['user_id']}:{page}",
                )
            )
            if len(row) == 2:
                keyboard.inline_keyboard.append(row)
                row = []
        if row:
            keyboard.inline_keyboard.append(row)
        nav = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(
                    text="Назад",
                    callback_data=f"betpage:{group_id}:{owner_id}:{bet_type}:{page - 1}",
                )
            )
        if page + 1 < total_pages:
            nav.append(
                InlineKeyboardButton(
                    text="Вперёд",
                    callback_data=f"betpage:{group_id}:{owner_id}:{bet_type}:{page + 1}",
                )
            )
        if nav:
            keyboard.inline_keyboard.append(nav)

        if isinstance(target, CallbackQuery):
            await safe_edit_message(target.message, text, reply_markup=keyboard)
            ctx.db.register_message_for_cleanup(
                group_id,
                target.message.chat.id,
                target.message.message_id,
                datetime.now().isoformat(),
            )
        else:
            sent = await target.answer(text, reply_markup=keyboard)
            ctx.db.register_message_for_cleanup(
                group_id,
                sent.chat.id,
                sent.message_id,
                datetime.now().isoformat(),
            )

    @router.message(Command("bet_day"))
    async def cmd_bet_day(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        ctx.db.upsert_user(
            message.chat.id,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        ctx.db.sync_user(
            message.chat.id,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        await send_bet_menu(message, message.chat.id, message.from_user.id, "day", 0)

    @router.message(Command("bet_evil"))
    async def cmd_bet_evil(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        ctx.db.upsert_user(
            message.chat.id,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        ctx.db.sync_user(
            message.chat.id,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        await send_bet_menu(message, message.chat.id, message.from_user.id, "evil", 0)

    @router.callback_query(F.data.startswith("betpage:"))
    async def cb_bet_page(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        owner_id = int(parts[2])
        bet_type = parts[3]
        page = int(parts[4])
        if callback.from_user.id != owner_id:
            await callback.answer("Эти кнопки только для автора.")
            return
        if callback.message is None or callback.message.chat.id != group_id:
            await callback.answer("Ошибка группы.")
            return
        if not await ensure_supported_group(ctx, callback):
            return
        ctx.db.sync_user(
            group_id,
            owner_id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name,
        )
        await send_bet_menu(callback, group_id, owner_id, bet_type, page)
        await callback.answer()

    @router.callback_query(F.data.startswith("betpick:"))
    async def cb_bet_pick(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        owner_id = int(parts[2])
        bet_type = parts[3]
        target_id = int(parts[4])
        page = int(parts[5])
        if callback.from_user.id != owner_id:
            await callback.answer("Эти кнопки только для автора.")
            return
        if callback.message is None or callback.message.chat.id != group_id:
            await callback.answer("Ошибка группы.")
            return
        if not await ensure_supported_group(ctx, callback):
            return
        ctx.db.sync_user(
            group_id,
            owner_id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name,
        )
        target = ctx.db.get_user_identity(group_id, target_id)
        if not target:
            await callback.answer("Игрок не найден.")
            return
        name = format_user_name(
            target_id,
            None,
            target.get("first_name"),
            target.get("last_name"),
        )
        bet_date = today_str(ctx.tz)
        current_amount = ctx.db.get_bet_amounts(group_id, owner_id, bet_type, bet_date).get(target_id, 0)
        desired_amount = max(ctx.config["bet_step"], current_amount)
        text = (
            f"Ставка на {bet_title(bet_type)}\n"
            f"Игрок: {name}\n"
            f"Текущая ставка: {current_amount}\n"
            f"Выбранная ставка: {desired_amount}\n"
            f"Ваши очки: {ctx.db.get_points(group_id, owner_id)}"
        )
        step = ctx.config["bet_step"]
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"-{step}",
                        callback_data=f"betamount:{group_id}:{owner_id}:{bet_type}:{target_id}:{desired_amount - step}:{page}",
                    ),
                    InlineKeyboardButton(
                        text=f"+{step}",
                        callback_data=f"betamount:{group_id}:{owner_id}:{bet_type}:{target_id}:{desired_amount + step}:{page}",
                    ),
                    InlineKeyboardButton(
                        text=f"-{step * 10}",
                        callback_data=f"betamount:{group_id}:{owner_id}:{bet_type}:{target_id}:{desired_amount - step * 10}:{page}",
                    ),
                    InlineKeyboardButton(
                        text=f"+{step * 10}",
                        callback_data=f"betamount:{group_id}:{owner_id}:{bet_type}:{target_id}:{desired_amount + step * 10}:{page}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="Сделать ставку",
                        callback_data=f"betapply:{group_id}:{owner_id}:{bet_type}:{target_id}:{desired_amount}:{page}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Назад к списку",
                        callback_data=f"betpage:{group_id}:{owner_id}:{bet_type}:{page}",
                    )
                ],
            ]
        )
        await safe_edit_message(callback.message, text, reply_markup=keyboard)
        ctx.db.register_message_for_cleanup(
            group_id,
            callback.message.chat.id,
            callback.message.message_id,
            datetime.now().isoformat(),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("betamount:"))
    async def cb_bet_amount(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        owner_id = int(parts[2])
        bet_type = parts[3]
        target_id = int(parts[4])
        desired_amount = int(parts[5])
        page = int(parts[6])
        if callback.from_user.id != owner_id:
            await callback.answer("Эти кнопки только для автора.")
            return
        if callback.message is None or callback.message.chat.id != group_id:
            await callback.answer("Ошибка группы.")
            return
        if not await ensure_supported_group(ctx, callback):
            return
        if desired_amount < 0:
            desired_amount = 0
        target = ctx.db.get_user_identity(group_id, target_id)
        if not target:
            await callback.answer("Игрок не найден.")
            return
        name = format_user_name(
            target_id,
            None,
            target.get("first_name"),
            target.get("last_name"),
        )
        bet_date = today_str(ctx.tz)
        current_amount = ctx.db.get_bet_amounts(group_id, owner_id, bet_type, bet_date).get(target_id, 0)
        text = (
            f"Ставка на {bet_title(bet_type)}\n"
            f"Игрок: {name}\n"
            f"Текущая ставка: {current_amount}\n"
            f"Выбранная ставка: {desired_amount}\n"
            f"Ваши очки: {ctx.db.get_points(group_id, owner_id)}"
        )
        step = ctx.config["bet_step"]
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"-{step}",
                        callback_data=f"betamount:{group_id}:{owner_id}:{bet_type}:{target_id}:{desired_amount - step}:{page}",
                    ),
                    InlineKeyboardButton(
                        text=f"+{step}",
                        callback_data=f"betamount:{group_id}:{owner_id}:{bet_type}:{target_id}:{desired_amount + step}:{page}",
                    ),
                    InlineKeyboardButton(
                        text=f"-{step * 10}",
                        callback_data=f"betamount:{group_id}:{owner_id}:{bet_type}:{target_id}:{desired_amount - step * 10}:{page}",
                    ),
                    InlineKeyboardButton(
                        text=f"+{step * 10}",
                        callback_data=f"betamount:{group_id}:{owner_id}:{bet_type}:{target_id}:{desired_amount + step * 10}:{page}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="Сделать ставку",
                        callback_data=f"betapply:{group_id}:{owner_id}:{bet_type}:{target_id}:{desired_amount}:{page}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Назад к списку",
                        callback_data=f"betpage:{group_id}:{owner_id}:{bet_type}:{page}",
                    )
                ],
            ]
        )
        await safe_edit_message(callback.message, text, reply_markup=keyboard)
        ctx.db.register_message_for_cleanup(
            group_id,
            callback.message.chat.id,
            callback.message.message_id,
            datetime.now().isoformat(),
        )
        await callback.answer()


    @router.callback_query(F.data.startswith("betapply:"))
    async def cb_bet_apply(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        owner_id = int(parts[2])
        bet_type = parts[3]
        target_id = int(parts[4])
        desired_amount = int(parts[5])
        page = int(parts[6])
        if callback.from_user.id != owner_id:
            await callback.answer("Эти кнопки только для автора.")
            return
        if callback.message is None or callback.message.chat.id != group_id:
            await callback.answer("Ошибка группы.")
            return
        if not await ensure_supported_group(ctx, callback):
            return
        ctx.db.upsert_user(
            group_id,
            owner_id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name,
        )
        ctx.db.sync_user(
            group_id,
            owner_id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name,
        )
        bet_date = today_str(ctx.tz)
        current_amount = ctx.db.get_bet_amounts(group_id, owner_id, bet_type, bet_date).get(target_id, 0)
        delta = desired_amount - current_amount
        if delta == 0:
            await callback.answer("Ставка уже установлена.")
            return
        ok, error = ctx.db.adjust_bet(group_id, owner_id, bet_type, target_id, bet_date, delta)
        if not ok:
            await callback.answer(error, show_alert=True)
            return
        await send_bet_menu(callback, group_id, owner_id, bet_type, page)
        await callback.answer("Ставка сохранена.")

    @router.message(Command("cancel_day"))
    async def cmd_cancel_day(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        refunded = ctx.db.cancel_bets(message.chat.id, message.from_user.id, "day", today_str(ctx.tz))
        await message.answer(f"Ставки отменены, возвращено очков: {refunded}.")

    @router.message(Command("cancel_evil"))
    async def cmd_cancel_evil(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        refunded = ctx.db.cancel_bets(message.chat.id, message.from_user.id, "evil", today_str(ctx.tz))
        await message.answer(f"Ставки отменены, возвращено очков: {refunded}.")

    @router.message(Command("my_bets"))
    async def cmd_my_bets(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        ctx.db.sync_user(
            message.chat.id,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        bet_date = today_str(ctx.tz)
        bets = ctx.db.list_active_bets(message.chat.id, message.from_user.id, bet_date)
        if not bets:
            await message.answer("Активных ставок нет.")
            return
        lines = ["Активные ставки:", ""]
        for bet in bets:
            target = ctx.db.get_user_identity(message.chat.id, bet["target_user_id"]) or {
                "user_id": bet["target_user_id"],
                "username": None,
                "first_name": None,
                "last_name": None,
            }
            name = format_user_name(
                target["user_id"],
                None,
                target.get("first_name"),
                target.get("last_name"),
            )
            lines.append(f"{bet_title(bet['bet_type'])}: {name} — {bet['amount']}")
        await message.answer("\n".join(lines))

    return router
