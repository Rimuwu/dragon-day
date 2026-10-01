import asyncio
from datetime import datetime
import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.card_cache import invalidate_user_cache
from utils.context import AppContext
from utils.custom_emojis import fmt_emoji
from utils.guards import ensure_group_message, ensure_participant, ensure_supported_group
from utils.helpers import format_user_name
from utils.time_utils import today_str


def get_router(ctx: AppContext) -> Router:
    router = Router()

    async def _play_daily_game(
        message: Message,
        game_type: str,
        dice_emoji: str,
        game_title: str,
        cmd_name: str,
        config_key: str,
        max_val: int,
    ) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        if not message.from_user:
            return
        if not await ensure_participant(ctx, message):
            return

        today = today_str(ctx.tz)
        ctx.db.upsert_user(
            message.chat.id,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )

        used = ctx.db.check_daily_game_used(message.chat.id, message.from_user.id, game_type, today)
        if used:
            await message.reply(
                f"{dice_emoji} Вы уже использовали {cmd_name} сегодня. Приходите завтра!"
            )
            return

        dice_msg = await ctx.bot.send_dice(chat_id=message.chat.id, emoji=dice_emoji)
        dice_value = dice_msg.dice.value

        points_map = ctx.config.get(config_key, {})
        points = points_map.get(str(dice_value), 0)
        is_max = dice_value >= max_val

        cur_streak, max_streak = ctx.db.record_daily_game(
            message.chat.id,
            message.from_user.id,
            game_type,
            today,
            dice_value,
            points,
            is_max,
        )
        invalidate_user_cache(message.chat.id, message.from_user.id)

        # Wait for dice animation to complete
        await asyncio.sleep(4.5)

        raw_user_name = format_user_name(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        user_name = html.escape(raw_user_name)

        points_str = f"+{points}" if points > 0 else str(points)
        streak_note = ""
        if is_max:
            streak_note = (
                f"\n⭐ <b>МАКСИМАЛЬНЫЙ РЕЗУЛЬТАТ!</b>\n"
                f"🔥 Серия максимумов: <b>{cur_streak} дн. подряд</b> (Рекорд: {max_streak} дн.)!"
            )

        sign_word = "очков"
        coin_e = fmt_emoji("coin", "🪙")
        result_text = (
            f"{dice_emoji} <b>{game_title}:</b> выпало <b>{dice_value}/{max_val}</b>\n"
            f"{coin_e} <b>{user_name}</b>, вы получаете <b>{points_str} {sign_word}</b>!{streak_note}"
        )
        try:
            await dice_msg.reply(result_text, parse_mode="HTML")
        except Exception:
            await message.answer(result_text, parse_mode="HTML")

    @router.message(Command("roll"))
    async def cmd_roll(message: Message) -> None:
        await _play_daily_game(
            message=message,
            game_type="dice",
            dice_emoji="🎲",
            game_title="Бросок кубика",
            cmd_name="/roll",
            config_key="dice_points",
            max_val=6,
        )

    @router.message(Command("basket", "basketball"))
    async def cmd_basket(message: Message) -> None:
        await _play_daily_game(
            message=message,
            game_type="basket",
            dice_emoji="🏀",
            game_title="Баскетбол",
            cmd_name="/basket",
            config_key="basket_points",
            max_val=5,
        )

    @router.message(Command("bowling", "bowl"))
    async def cmd_bowling(message: Message) -> None:
        await _play_daily_game(
            message=message,
            game_type="bowling",
            dice_emoji="🎳",
            game_title="Боулинг",
            cmd_name="/bowling",
            config_key="bowling_points",
            max_val=6,
        )

    @router.message(Command("football", "soccer", "foot"))
    async def cmd_football(message: Message) -> None:
        await _play_daily_game(
            message=message,
            game_type="football",
            dice_emoji="⚽",
            game_title="Футбол",
            cmd_name="/football",
            config_key="football_points",
            max_val=5,
        )

    return router

