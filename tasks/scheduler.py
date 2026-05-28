import asyncio
import random
from datetime import datetime, timedelta

from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter

from utils.context import AppContext
from utils.helpers import compute_coef, format_user_name
from utils.phrases import pick_phrase
from utils.time_utils import parse_range, parse_time_str, pick_random_time, sleep_window_for_date, today_str


def _build_sleep_keyboard(group_id: int, sleep_date: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Участвовать", callback_data=f"sleepjoin:{group_id}:{sleep_date}")]
        ]
    )


async def _pick_valid_member(ctx: AppContext, group_id: int, candidates: list[dict]) -> dict | None:
    if not candidates:
        return None
    shuffled = candidates[:]
    random.shuffle(shuffled)
    for person in shuffled:
        try:
            member = await ctx.bot.get_chat_member(group_id, person["user_id"])
        except TelegramBadRequest as e:
            msg = str(e)
            if "PARTICIPANT_ID_INVALID" in msg or "USER_ID_INVALID" in msg or "user not found" in msg.lower():
                try:
                    ctx.db.remove_participant(group_id, person["user_id"])
                except Exception:
                    pass
                continue
            else:
                continue
        except (TelegramNetworkError, TelegramRetryAfter, Exception):
            continue
        if member.status not in ("left", "kicked"):
            return person
    return None


async def process_daily(ctx: AppContext, group_id: int, state: dict, send_day: bool, send_evil: bool) -> None:
    today = today_str(ctx.tz)
    if not send_day and not send_evil:
        return
    participants = ctx.db.list_participants(group_id)
    if not participants:
        await ctx.bot.send_message(group_id, "Сегодня нет участников для выбора драконов.")
        return

    day_winner = await _pick_valid_member(ctx, group_id, participants)
    if not day_winner:
        await ctx.bot.send_message(group_id, "Нет доступных участников в группе.")
        return

    remaining = [p for p in participants if p["user_id"] != day_winner["user_id"]]
    evil_winner = await _pick_valid_member(ctx, group_id, remaining) if remaining else day_winner

    if send_day:
        day_stats = ctx.db.get_user_stats(group_id, day_winner["user_id"]) or {}
        day_wins_total = (
            day_stats.get("wins_day", 0)
            + day_stats.get("wins_evil", 0)
            + day_stats.get("wins_sleepy", 0)
        )
        day_coef = compute_coef(day_wins_total, ctx.config)
        day_bets = ctx.db.settle_bets(group_id, "day", today, day_winner["user_id"], day_coef)
        ctx.db.record_win(group_id, day_winner["user_id"], "day", ctx.config["points_day"])

        day_name = format_user_name(
            day_winner["user_id"],
            day_winner.get("username"),
            day_winner.get("first_name"),
            day_winner.get("last_name"),
        )
        day_phrase = pick_phrase("day")
        day_caption = f"Дракон дня: {day_name}\n+{ctx.config['points_day']} очков"
        if day_bets:
            won_points = day_bets.get("won_points", 0)
            lost_points = day_bets.get("lost_points", 0)
            winners = day_bets.get("winning_bets", [])
            lines = [
                f"\nСтавки: +{won_points} / -{lost_points}",
            ]
            if winners:
                lines.append("Первые 5 сыгравших:")
                for bet in winners:
                    bettor = ctx.db.get_user_identity(group_id, bet["user_id"]) or {
                        "user_id": bet["user_id"],
                        "username": None,
                        "first_name": None,
                        "last_name": None,
                    }
                    bettor_name = format_user_name(
                        bettor["user_id"],
                        bettor.get("username"),
                        bettor.get("first_name"),
                        bettor.get("last_name"),
                    )
                    lines.append(f"- {bettor_name}: {bet['amount']} -> {bet['payout']}")
            day_caption = f"{day_caption}\n" + "\n".join(lines)
        if day_phrase:
            day_caption = f"{day_caption}\n\n{day_phrase}"
        await ctx.bot.send_photo(group_id, FSInputFile(ctx.config["images"]["day"]), caption=day_caption)

    if evil_winner and send_evil:
        evil_stats = ctx.db.get_user_stats(group_id, evil_winner["user_id"]) or {}
        evil_wins_total = (
            evil_stats.get("wins_day", 0)
            + evil_stats.get("wins_evil", 0)
            + evil_stats.get("wins_sleepy", 0)
        )
        evil_coef = compute_coef(evil_wins_total, ctx.config)
        evil_bets = ctx.db.settle_bets(group_id, "evil", today, evil_winner["user_id"], evil_coef)
        ctx.db.record_win(group_id, evil_winner["user_id"], "evil", ctx.config["points_evil"])
        evil_name = format_user_name(
            evil_winner["user_id"],
            evil_winner.get("username"),
            evil_winner.get("first_name"),
            evil_winner.get("last_name"),
        )
        evil_phrase = pick_phrase("evil")
        evil_caption = f"Злой дракон: {evil_name}\n{ctx.config['points_evil']} очков"
        if evil_bets:
            won_points = evil_bets.get("won_points", 0)
            lost_points = evil_bets.get("lost_points", 0)
            winners = evil_bets.get("winning_bets", [])
            lines = [
                f"\nСтавки: +{won_points} / -{lost_points}",
            ]
            if winners:
                lines.append("Первые 5 сыгравших:")
                for bet in winners:
                    bettor = ctx.db.get_user_identity(group_id, bet["user_id"]) or {
                        "user_id": bet["user_id"],
                        "username": None,
                        "first_name": None,
                        "last_name": None,
                    }
                    bettor_name = format_user_name(
                        bettor["user_id"],
                        bettor.get("username"),
                        bettor.get("first_name"),
                        bettor.get("last_name"),
                    )
                    lines.append(f"- {bettor_name}: {bet['amount']} -> {bet['payout']}")
            evil_caption = f"{evil_caption}\n" + "\n".join(lines)
        if evil_phrase:
            evil_caption = f"{evil_caption}\n\n{evil_phrase}"
        await ctx.bot.send_photo(group_id, FSInputFile(ctx.config["images"]["evil"]), caption=evil_caption)

    ctx.db.set_group_state(
        group_id,
        today if send_day else state["last_daily_date"],
        today if send_evil else state["last_evil_date"],
        state["last_sleepy_date"],
        state["next_sleepy_at"],
        ctx.config,
    )


async def process_sleepy(ctx: AppContext, group_id: int, sleep_date: str) -> None:
    join_minutes = int(ctx.config["sleep_join_minutes"])
    close_at = datetime.now(ctx.tz) + timedelta(minutes=join_minutes)
    keyboard = _build_sleep_keyboard(group_id, sleep_date)
    msg = await ctx.bot.send_message(
        group_id,
        f"Ночной дракон открыт! Участвуйте в течение {join_minutes} минут.",
        reply_markup=keyboard,
    )
    ctx.db.create_sleep_event(group_id, sleep_date, close_at.isoformat(), msg.message_id)
    await asyncio.sleep(join_minutes * 60)
    try:
        await ctx.bot.delete_message(group_id, msg.message_id)
    except Exception:
        pass
    ctx.db.delete_sleep_event(group_id, sleep_date)

    entries = ctx.db.get_sleep_entries(group_id, sleep_date)
    if not entries:
        await ctx.bot.send_message(group_id, "Никто не участвовал в ночном драконе сегодня.")
        return

    random.shuffle(entries)
    winner_id = None
    for user_id in entries:
        member = await ctx.bot.get_chat_member(group_id, user_id)
        if member.status not in ("left", "kicked"):
            winner_id = user_id
            break

    if winner_id is None:
        await ctx.bot.send_message(group_id, "Победитель не найден — никто не в группе.")
        return

    ctx.db.record_win(group_id, winner_id, "sleepy", ctx.config["points_sleepy"])
    winner_stats = ctx.db.get_user_stats(group_id, winner_id) or {}
    winner_name = format_user_name(
        winner_id,
        winner_stats.get("username"),
        winner_stats.get("first_name"),
        winner_stats.get("last_name"),
    )
    sleepy_phrase = pick_phrase("sleepy")
    caption = f"Сонный дракон: {winner_name}\n+{ctx.config['points_sleepy']} очков"
    if sleepy_phrase:
        caption = f"{caption}\n\n{sleepy_phrase}"
    await ctx.bot.send_photo(group_id, FSInputFile(ctx.config["images"]["sleepy"]), caption=caption)
    ctx.db.clear_sleep_entries(group_id, sleep_date)


async def scheduler_loop(ctx: AppContext) -> None:
    while True:
        now = datetime.now(ctx.tz)
        today = now.date().isoformat()
        for group_id in ctx.db.get_groups():
            settings = ctx.db.get_group_settings(group_id, ctx.config)
            state = ctx.db.get_group_state(group_id, ctx.config)
            daily_time = parse_time_str(settings["daily_time"])
            daily_dt = datetime.combine(now.date(), daily_time, tzinfo=ctx.tz)

            send_day = state["last_daily_date"] != today
            send_evil = state["last_evil_date"] != today
            if now >= daily_dt and (send_day or send_evil):
                ctx.db.set_group_state(
                    group_id,
                    today if send_day else state["last_daily_date"],
                    today if send_evil else state["last_evil_date"],
                    state["last_sleepy_date"],
                    state["next_sleepy_at"],
                    ctx.config,
                )
                asyncio.create_task(process_daily(ctx, group_id, state, send_day, send_evil))

            next_sleepy_raw = state["next_sleepy_at"]
            next_sleepy_at = None
            if next_sleepy_raw:
                try:
                    next_sleepy_at = datetime.fromisoformat(next_sleepy_raw)
                except ValueError:
                    next_sleepy_at = None

            if state["last_sleepy_date"] != today and next_sleepy_at is None:
                start_time, end_time = parse_range(f"{settings['sleep_start']}-{settings['sleep_end']}")
                start_dt, end_dt = sleep_window_for_date(now, start_time, end_time, ctx.tz)
                if now >= end_dt:
                    start_dt, end_dt = sleep_window_for_date(now + timedelta(days=1), start_time, end_time, ctx.tz)
                if now > start_dt:
                    start_dt = now
                next_sleepy_at = pick_random_time(start_dt, end_dt)
                ctx.db.set_group_state(
                    group_id,
                    state["last_daily_date"],
                    state["last_evil_date"],
                    state["last_sleepy_date"],
                    next_sleepy_at.isoformat(),
                    ctx.config,
                )

            if next_sleepy_at and now >= next_sleepy_at and state["last_sleepy_date"] != today:
                ctx.db.set_group_state(
                    group_id,
                    state["last_daily_date"],
                    state["last_evil_date"],
                    today,
                    None,
                    ctx.config,
                )
                sleep_date = next_sleepy_at.date().isoformat()
                asyncio.create_task(process_sleepy(ctx, group_id, sleep_date))

        await asyncio.sleep(30)


async def cleanup_loop(ctx: AppContext) -> None:
    while True:
        try:
            timeout = ctx.config.get("cleanup_message_timeout", 3600)
            stale = ctx.db.get_stale_messages(timeout)
            for msg_info in stale:
                try:
                    await ctx.bot.edit_message_text(
                        text="Это сообщение устарело, воспользуйтесь командой заново.",
                        chat_id=msg_info["chat_id"],
                        message_id=msg_info["message_id"],
                        reply_markup=None
                    )
                except Exception:
                    pass
                try:
                    ctx.db.delete_cleanup_record(
                        msg_info["group_id"],
                        msg_info["chat_id"],
                        msg_info["message_id"],
                    )
                except Exception:
                    pass
        except Exception:
            pass
        await asyncio.sleep(30)


async def start_scheduler(ctx: AppContext) -> None:
    asyncio.create_task(scheduler_loop(ctx))
    asyncio.create_task(cleanup_loop(ctx))
