import asyncio
import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, CallbackQuery, InputMediaPhoto, Message

from handlers.profile import fetch_user_avatar
from utils.card_cache import (
    get_cached_general,
    set_cached_general,
    update_cached_general_file_id,
)
from utils.context import AppContext
from utils.guards import ensure_group_message, ensure_participant, ensure_supported_group
from utils.helpers import format_user_name
from utils.keyboards import build_leaderboard_keyboard
from utils.leaderboard_card import render_leaderboard_podium
from utils.member import resolve_user_display
from utils.texts import build_leaderboard_text

logger = logging.getLogger(__name__)

PAGE_SIZE = 10


def get_router(ctx: AppContext) -> Router:
    router = Router()

    async def get_or_render_podium(group_id: int, kind: str, top_players: list[dict]) -> tuple[bytes, str | None]:
        cache_key = f"lb_podium:{group_id}:{kind}"
        cached = get_cached_general(cache_key)
        if cached is not None:
            return cached

        # Fetch avatars for top 3 players
        for p in top_players[:3]:
            p["avatar_bytes"] = await fetch_user_avatar(ctx.bot, p["user_id"])

        buf = render_leaderboard_podium(top_players[:3], kind=kind)
        card_bytes = buf.getvalue()
        set_cached_general(cache_key, card_bytes)
        return card_bytes, None

    async def send_leaderboard(
        target: Message | CallbackQuery,
        group_id: int,
        owner_id: int,
        kind: str,
        page: int,
        previous_kind: str | None = None,
    ) -> None:
        entries = ctx.db.get_leaderboard_all(group_id, kind)
        valid_entries = []
        for entry in entries:
            username, first_name, last_name = await resolve_user_display(
                ctx,
                group_id,
                entry["user_id"],
                entry.get("username"),
                entry.get("first_name"),
                entry.get("last_name"),
            )
            if username or first_name or last_name:
                entry["username"] = username
                entry["first_name"] = first_name
                entry["last_name"] = last_name
                entry["display_name"] = format_user_name(
                    entry["user_id"], username, first_name, last_name
                )
                valid_entries.append(entry)
            else:
                continue

        total = len(valid_entries)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        if page >= total_pages:
            page = max(0, total_pages - 1)
        offset = page * PAGE_SIZE
        page_items = valid_entries[offset : offset + PAGE_SIZE]
        text = build_leaderboard_text(kind, page_items, page, total, PAGE_SIZE)
        keyboard = build_leaderboard_keyboard(group_id, owner_id, kind, page, total, PAGE_SIZE)

        cache_key = f"lb_podium:{group_id}:{kind}"

        if isinstance(target, CallbackQuery):
            msg = target.message
            if msg is None:
                return

            # If kind changed or message has no photo, update media
            if previous_kind is not None and previous_kind != kind:
                card_bytes, file_id = await get_or_render_podium(group_id, kind, valid_entries[:3])
                media = file_id if file_id else BufferedInputFile(card_bytes, filename=f"podium_{group_id}_{kind}.png")
                try:
                    res = await msg.edit_media(
                        media=InputMediaPhoto(media=media, caption=text, parse_mode="HTML"),
                        reply_markup=keyboard,
                    )
                    if res and getattr(res, "photo", None):
                        update_cached_general_file_id(cache_key, res.photo[-1].file_id)
                except TelegramBadRequest as e:
                    if "message is not modified" not in str(e):
                        logger.debug("Failed to edit media: %s", e)
            else:
                # Same kind, only page changed: edit caption directly
                try:
                    await msg.edit_caption(caption=text, parse_mode="HTML", reply_markup=keyboard)
                except TelegramBadRequest as e:
                    if "message is not modified" not in str(e):
                        # Fallback to edit_text if message wasn't a photo
                        try:
                            await msg.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
                        except Exception:
                            pass

            ctx.db.register_message_for_cleanup(
                group_id,
                msg.chat.id,
                msg.message_id,
                datetime.now().isoformat(),
            )
        else:
            # Initial command /leaderboard
            card_bytes, file_id = await get_or_render_podium(group_id, kind, valid_entries[:3])
            sent = None

            if file_id:
                try:
                    sent = await target.answer_photo(
                        photo=file_id,
                        caption=text,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )
                except Exception as e_fid:
                    logger.debug("Sending with cached file_id failed: %s", e_fid)
                    sent = None

            if not sent:
                photo_file = BufferedInputFile(card_bytes, filename=f"podium_{group_id}_{kind}.png")
                sent = await target.answer_photo(
                    photo=photo_file,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )

            if sent and sent.photo:
                update_cached_general_file_id(cache_key, sent.photo[-1].file_id)

            if sent:
                ctx.db.register_message_for_cleanup(
                    group_id,
                    sent.chat.id,
                    sent.message_id,
                    datetime.now().isoformat(),
                )

    @router.message(Command("leaderboard"))
    async def cmd_leaderboard(message: Message, command: CommandObject) -> None:
        if not ensure_group_message(message):
            await message.answer("Команда доступна только в группах.")
            return
        if not await ensure_supported_group(ctx, message):
            return
        if not message.from_user:
            return
        if not await ensure_participant(ctx, message):
            return
        ctx.db.sync_user(
            message.chat.id,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        args = (command.args or "").strip().lower()
        kind = args if args in {"day", "evil", "sleepy", "points"} else "points"
        await send_leaderboard(message, message.chat.id, message.from_user.id, kind, 0)

    @router.callback_query(F.data.startswith("lb:"))
    async def cb_leaderboard(callback: CallbackQuery) -> None:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        owner_id = int(parts[2])
        kind = parts[3]
        page = int(parts[4])
        if callback.from_user.id != owner_id:
            await callback.answer("Эти кнопки только для автора команды.")
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

        # Detect previous kind from current buttons if possible
        prev_kind = None
        if callback.message.reply_markup:
            for row in callback.message.reply_markup.inline_keyboard:
                for btn in row:
                    if btn.text and btn.text.startswith("• "):
                        # Found active tab
                        for k, l in [("points", "Очки"), ("day", "День"), ("evil", "Зло"), ("sleepy", "Сон")]:
                            if l in btn.text:
                                prev_kind = k
                                break

        await send_leaderboard(callback, group_id, owner_id, kind, page, previous_kind=prev_kind)
        await callback.answer()

    return router
