from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from utils.context import AppContext
from utils.caption import build_dragon_caption
from utils.guards import ensure_group_message, ensure_supported_group
from utils.helpers import format_user_name, compute_coef
from utils.member import pick_valid_member
from utils.time_utils import today_str


def get_router(ctx: AppContext) -> Router:
    router = Router()

    @router.message(Command("add_group"))
    async def cmd_add_group(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if message.from_user is None:
            return
        if message.from_user.id != ctx.admin_id:
            await message.answer("Команда доступна только администратору бота.")
            return
        added = ctx.db.allow_group(
            message.chat.id,
            message.from_user.id,
            datetime.now(ctx.tz).isoformat(),
            ctx.config,
        )
        if added:
            await message.answer("Группа добавлена и готова к работе.")
        else:
            await message.answer("Группа уже добавлена.")

    @router.message(Command("points"))
    async def cmd_points(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        if message.from_user is None:
            return
        if message.from_user.id != ctx.admin_id:
            await message.answer("Команда доступна только администратору бота.")
            return
        args = (message.text or "").split()
        if len(args) < 2:
            await message.answer("Использование: /points <delta> (ответом на сообщение) или /points <user_id> <delta>.")
            return
        if message.reply_to_message and message.reply_to_message.from_user and len(args) == 2:
            target_id = message.reply_to_message.from_user.id
            delta_raw = args[1]
        elif len(args) >= 3:
            target_id = int(args[1])
            delta_raw = args[2]
        else:
            await message.answer("Укажите пользователя и изменение очков.")
            return
        try:
            delta = int(delta_raw)
        except ValueError:
            await message.answer("Неверное значение очков.")
            return
        ctx.db.adjust_points(message.chat.id, target_id, delta)
        await message.answer(f"Очки обновлены: {target_id} ({delta:+d}).")

    @router.message(Command("repick"))
    async def cmd_repick(message: Message) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        if message.from_user is None:
            return
        if message.from_user.id != ctx.admin_id:
            await message.answer("Команда доступна только администратору бота.")
            return
        args = (message.text or "").split()
        if len(args) < 2 or args[1] not in ("day", "evil"):
            await message.answer("Использование: /repick <day|evil>")
            return
        
        bet_type = args[1]
        today = today_str(ctx.tz)
        participants = ctx.db.list_participants(message.chat.id)
        if not participants:
            await message.answer("Нет участников для переигрывания.")
            return
        
        winner = await pick_valid_member(ctx, message.chat.id, participants)
        
        if not winner:
            await message.answer("Нет доступных участников.")
            return
        
        # Settle bets and record win
        stats = ctx.db.get_user_stats(message.chat.id, winner["user_id"]) or {}
        wins_total = stats.get("wins_day", 0) + stats.get("wins_evil", 0) + stats.get("wins_sleepy", 0)
        coef = compute_coef(wins_total, ctx.config)
        bets_result = ctx.db.settle_bets(message.chat.id, bet_type, today, winner["user_id"], coef)
        
        group_settings = ctx.db.get_group_settings(message.chat.id, ctx.config)
        points = group_settings["points_day"] if bet_type == "day" else group_settings["points_evil"]
        ctx.db.record_win(message.chat.id, winner["user_id"], bet_type, points)
        
        caption = await build_dragon_caption(ctx, message.chat.id, winner, bet_type, points, bets_result)
        winner_name = format_user_name(
            winner["user_id"],
            winner.get("username"),
            winner.get("first_name"),
            winner.get("last_name"),
        )
        title = "Дракон дня" if bet_type == "day" else "Злой дракон"
        
        image_key = bet_type
        await ctx.bot.send_photo(message.chat.id, FSInputFile(ctx.config["images"][image_key]), caption=caption)
        await message.answer(f"Переиграно: {title} — {winner_name}")

    return router