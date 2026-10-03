import asyncio
import random
from datetime import datetime, timedelta

from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from utils.context import AppContext
from utils.helpers import compute_coef
from utils.caption import build_dragon_caption
from utils.keyboards import build_sleep_keyboard
from utils.member import pick_valid_member
from utils.time_utils import parse_range, parse_time_str, pick_random_time, sleep_window_for_date, today_str


def _build_sleep_keyboard(group_id: int, sleep_date: str, count: int = 0) -> InlineKeyboardMarkup:
    return build_sleep_keyboard(group_id, sleep_date, count=count)


async def process_daily(
    ctx: AppContext,
    group_id: int,
    settings: dict,
    state: dict,
    send_day: bool,
    send_evil: bool,
) -> None:
    today = today_str(ctx.tz)
    if not send_day and not send_evil:
        return
    dragons_topic_id = settings.get("dragons_topic_id")
    participants = ctx.db.list_participants(group_id)
    if not participants:
        await ctx.bot.send_message(group_id, "Сегодня нет участников для выбора драконов.", message_thread_id=dragons_topic_id)
        return

    # 1. Day Dragon: pick from candidate pool
    day_pool = ctx.db.get_or_create_bet_pool(group_id, "day", today, ctx.config, participants)
    candidates_day = day_pool if day_pool else participants
    day_winner = await pick_valid_member(ctx, group_id, candidates_day, "day")
    if not day_winner and candidates_day != participants:
        day_winner = await pick_valid_member(ctx, group_id, participants, "day")

    if not day_winner:
        await ctx.bot.send_message(group_id, "Нет доступных участников в группе.", message_thread_id=dragons_topic_id)
        return

    # 2. Evil Dragon: pick from candidate pool (excluding day winner)
    evil_pool = ctx.db.get_or_create_bet_pool(group_id, "evil", today, ctx.config, participants)
    remaining_evil = [p for p in evil_pool if p["user_id"] != day_winner["user_id"]]
    if not remaining_evil:
        remaining_evil = [p for p in participants if p["user_id"] != day_winner["user_id"]]

    evil_winner = await pick_valid_member(ctx, group_id, remaining_evil, "evil") if remaining_evil else day_winner

    if send_day:
        day_stats = ctx.db.get_user_stats(group_id, day_winner["user_id"]) or {}
        day_wins_total = (
            day_stats.get("wins_day", 0)
            + day_stats.get("wins_evil", 0)
            + day_stats.get("wins_sleepy", 0)
        )
        day_coef = compute_coef(day_wins_total, ctx.config)
        day_bets = ctx.db.settle_bets(group_id, "day", today, day_winner["user_id"], day_coef)
        ctx.db.record_win(group_id, day_winner["user_id"], "day", settings["points_day"], today)

        from utils.effects import apply_dragon_effect
        day_effect = apply_dragon_effect(ctx, group_id, "day", day_winner["user_id"], today)
        day_caption = await build_dragon_caption(ctx, group_id, day_winner, "day", settings["points_day"], day_bets, effect=day_effect)
        await ctx.bot.send_photo(
            group_id,
            FSInputFile(ctx.config["images"]["day"]),
            caption=day_caption,
            parse_mode="HTML",
            message_thread_id=dragons_topic_id,
        )

    if evil_winner and send_evil:
        evil_stats = ctx.db.get_user_stats(group_id, evil_winner["user_id"]) or {}
        evil_wins_total = (
            evil_stats.get("wins_day", 0)
            + evil_stats.get("wins_evil", 0)
            + evil_stats.get("wins_sleepy", 0)
        )
        evil_coef = compute_coef(evil_wins_total, ctx.config)
        evil_bets = ctx.db.settle_bets(group_id, "evil", today, evil_winner["user_id"], evil_coef)
        ctx.db.record_win(group_id, evil_winner["user_id"], "evil", settings["points_evil"], today)

        from utils.effects import apply_dragon_effect
        evil_effect = apply_dragon_effect(ctx, group_id, "evil", evil_winner["user_id"], today)
        evil_caption = await build_dragon_caption(ctx, group_id, evil_winner, "evil", settings["points_evil"], evil_bets, effect=evil_effect)
        await ctx.bot.send_photo(
            group_id,
            FSInputFile(ctx.config["images"]["evil"]),
            caption=evil_caption,
            parse_mode="HTML",
            message_thread_id=dragons_topic_id,
        )

    ctx.db.set_group_state(
        group_id,
        today if send_day else state["last_daily_date"],
        today if send_evil else state["last_evil_date"],
        state["last_sleepy_date"],
        state["next_sleepy_at"],
        ctx.config,
    )


async def process_sleepy(ctx: AppContext, group_id: int, sleep_date: str) -> None:
    settings = ctx.db.get_group_settings(group_id, ctx.config)
    dragons_topic_id = settings.get("dragons_topic_id")
    join_minutes = int(ctx.config["sleep_join_minutes"])
    close_at = datetime.now(ctx.tz) + timedelta(minutes=join_minutes)
    count = ctx.db.count_sleep_entries(group_id, sleep_date)
    keyboard = build_sleep_keyboard(group_id, sleep_date, count)
    msg = await ctx.bot.send_message(
        group_id,
        f"Ночной дракон открыт! Участвуйте в течение {join_minutes} минут.",
        reply_markup=keyboard,
        message_thread_id=dragons_topic_id,
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
        await ctx.bot.send_message(
            group_id,
            "Никто не участвовал в ночном драконе сегодня.",
            message_thread_id=dragons_topic_id,
        )
        return

    candidate_dicts = [{"user_id": uid} for uid in entries]

    winner_person = await pick_valid_member(ctx, group_id, candidate_dicts, "sleepy")
    if not winner_person:
        await ctx.bot.send_message(
            group_id,
            "Победитель не найден — никто не в группе.",
            message_thread_id=dragons_topic_id,
        )
        ctx.db.clear_sleep_entries(group_id, sleep_date)
        return

    winner_id = winner_person["user_id"]
    ctx.db.record_win(group_id, winner_id, "sleepy", settings["points_sleepy"], sleep_date)
    winner_stats = ctx.db.get_user_stats(group_id, winner_id) or {}
    winner_dict = {
        "user_id": winner_id,
        "username": winner_stats.get("username") or winner_person.get("username"),
        "first_name": winner_stats.get("first_name") or winner_person.get("first_name"),
        "last_name": winner_stats.get("last_name") or winner_person.get("last_name"),
    }
    caption = await build_dragon_caption(ctx, group_id, winner_dict, "sleepy", settings["points_sleepy"])
    await ctx.bot.send_photo(
        group_id,
        FSInputFile(ctx.config["images"]["sleepy"]),
        caption=caption,
        parse_mode="HTML",
        message_thread_id=dragons_topic_id,
    )
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
                asyncio.create_task(process_daily(ctx, group_id, settings, state, send_day, send_evil))

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
                    await ctx.bot.delete_message(
                        chat_id=msg_info["chat_id"],
                        message_id=msg_info["message_id"],
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


async def lottery_loop(ctx: AppContext) -> None:
    import html
    from aiogram.types import BufferedInputFile
    from utils.custom_emojis import fmt_emoji
    from utils.helpers import format_user_name
    from utils.lottery_card import render_lottery_card

    while True:
        try:
            expired = ctx.db.get_expired_active_lotteries()
            for lot_meta in expired:
                lot_id = lot_meta["id"]
                group_id = lot_meta["group_id"]
                res = ctx.db.finish_lottery(lot_id)
                if not res:
                    continue

                if res.get("canceled"):
                    creator_id = res["creator_id"]
                    creator_ident = ctx.db.get_user_identity(group_id, creator_id) or {}
                    creator_name = html.escape(
                        format_user_name(
                            creator_id,
                            creator_ident.get("username"),
                            creator_ident.get("first_name"),
                            creator_ident.get("last_name"),
                        )
                    )
                    await ctx.bot.send_message(
                        group_id,
                        f"🎟️ <b>Лотерея #{lot_id} завершена.</b>\n"
                        f"Не набралось достаточного количества участников (минимум 2).\n"
                        f"Ставка возвращена {creator_name}.",
                        parse_mode="HTML",
                    )
                else:
                    winner_id = res["winner_id"]
                    winner_ident = ctx.db.get_user_identity(group_id, winner_id) or {}
                    winner_name = html.escape(
                        format_user_name(
                            winner_id,
                            winner_ident.get("username"),
                            winner_ident.get("first_name"),
                            winner_ident.get("last_name"),
                        )
                    )
                    winning_ticket = res["winning_ticket"]
                    total_pot = res["total_pot"]
                    bet = res["bet"]
                    sold_tickets = res.get("sold_tickets", [])
                    total_sold = len(sold_tickets)

                    card_buf = render_lottery_card(
                        prize=total_pot,
                        ticket_price=bet,
                        sold_count=total_sold,
                        sold_tickets=sold_tickets,
                        winning_ticket=winning_ticket,
                    )

                    coin_e = fmt_emoji("coin", "🪙")
                    crown_e = fmt_emoji("crown", "👑")

                    caption = (
                        f"🏆 <b>ИТОГИ КОРОЛЕВСКОЙ ЛОТЕРЕИ #{lot_id}!</b>\n"
                        f"────────────────────\n"
                        f"🎟️ <b>Выигрышный билет:</b> <code>#{winning_ticket:03d}</code>\n"
                        f"{crown_e} <b>Победитель:</b> {winner_name}\n"
                        f"{coin_e} <b>Выигрышный куш:</b> <b>{total_pot:,} очков</b>\n"
                        f"────────────────────\n"
                        f"<i>Всего билетов в розыгрыше: {total_sold} шт.</i>"
                    ).replace(",", " ")

                    photo = BufferedInputFile(card_buf.getvalue(), filename=f"lottery_result_{lot_id}.png")
                    sent = await ctx.bot.send_photo(
                        chat_id=group_id,
                        photo=photo,
                        caption=caption,
                        parse_mode="HTML",
                    )
                    if sent:
                        ctx.db.register_message_for_cleanup(
                            group_id,
                            sent.chat.id,
                            sent.message_id,
                            datetime.now().isoformat(),
                        )
        except Exception as e:
            pass

        await asyncio.sleep(20)


async def start_scheduler(ctx: AppContext) -> None:
    asyncio.create_task(scheduler_loop(ctx))
    asyncio.create_task(cleanup_loop(ctx))
    asyncio.create_task(lottery_loop(ctx))
