from datetime import datetime
import html

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from utils.context import AppContext
from utils.caption import build_dragon_caption
from utils.guards import ensure_group_message, ensure_supported_group
from utils.helpers import compute_coef, format_leaderboard_user_name, format_user_name
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
            target_user = message.reply_to_message.from_user
            target_id = target_user.id
            ctx.db.upsert_user(
                message.chat.id,
                target_user.id,
                target_user.username,
                target_user.first_name,
                target_user.last_name,
            )
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
        
        winner = await pick_valid_member(ctx, message.chat.id, participants, bet_type)
        
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
        ctx.db.record_win(message.chat.id, winner["user_id"], bet_type, points, today)
        
        from utils.effects import apply_dragon_effect
        effect = apply_dragon_effect(ctx, message.chat.id, bet_type, winner["user_id"], today)
        caption = await build_dragon_caption(ctx, message.chat.id, winner, bet_type, points, bets_result, effect=effect)
        winner_name = format_user_name(
            winner["user_id"],
            winner.get("username"),
            winner.get("first_name"),
            winner.get("last_name"),
        )
        title = "Дракон дня" if bet_type == "day" else "Злой дракон"
        
        image_key = bet_type
        dragons_topic_id = group_settings.get("dragons_topic_id")
        await ctx.bot.send_photo(
            message.chat.id,
            FSInputFile(ctx.config["images"][image_key]),
            caption=caption,
            parse_mode="HTML",
            message_thread_id=dragons_topic_id,
        )
        await message.answer(f"Переиграно: {title} — {winner_name}")

    def _build_shadow_list_message() -> tuple[str, InlineKeyboardMarkup | None]:
        users = ctx.db.list_shadow_users()
        if not users:
            return (
                "🔒 <b>Теневой пул пуст.</b>\n\n"
                "<i>Команды:</i>\n"
                "• <code>/shadow &lt;user_id&gt;</code> — добавить пользователя\n"
                "• <code>/shadow del &lt;user_id&gt;</code> — удалить пользователя",
                None,
            )

        lines = [
            f"🔒 <b>Теневой пул пользователей ({len(users)}):</b>",
            "────────────────────",
        ]
        keyboard_rows = []
        for idx, u in enumerate(users, start=1):
            name = html.escape(format_leaderboard_user_name(u["user_id"], u.get("username"), u.get("first_name"), u.get("last_name")))
            lines.append(f"<b>{idx}.</b> {name} (<code>{u['user_id']}</code>)")
            btn_label = f"❌ Удалить {u['user_id']}"
            keyboard_rows.append([
                InlineKeyboardButton(text=btn_label, callback_data=f"sb_del:{u['user_id']}")
            ])

        lines.append("────────────────────")
        lines.append("<i>Пользователи в этом пуле с вероятностью 99% не побеждают в драконах, дуэлях и лотерее.</i>")

        keyboard_rows.append([
            InlineKeyboardButton(text="🔄 Обновить", callback_data="sb_ref")
        ])
        return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    @router.message(Command("shadow", "shadowban", "sb"))
    async def cmd_shadow(message: Message, command: CommandObject) -> None:
        if message.chat.type != "private":
            return
        if not message.from_user or message.from_user.id != ctx.admin_id:
            return

        args = (command.args or "").strip().split()
        if not args:
            text, kb = _build_shadow_list_message()
            await message.answer(text, parse_mode="HTML", reply_markup=kb)
            return

        subcmd = args[0].lower()
        if subcmd in ("del", "delete", "rem", "remove", "-"):
            if len(args) < 2:
                await message.answer("Укажите user_id: <code>/shadow del &lt;user_id&gt;</code>", parse_mode="HTML")
                return
            try:
                target_uid = int(args[1])
            except ValueError:
                await message.answer("Некорректный ID пользователя.")
                return
            ok = ctx.db.remove_shadow_user(target_uid)
            if ok:
                await message.answer(f"✅ Пользователь ID <code>{target_uid}</code> удален из теневого пула.", parse_mode="HTML")
            else:
                await message.answer(f"Пользователь ID <code>{target_uid}</code> не найден в теневом пуле.", parse_mode="HTML")
            return

        try:
            target_uid = int(args[0])
        except ValueError:
            await message.answer("Укажите числовой user_id: <code>/shadow &lt;user_id&gt;</code>", parse_mode="HTML")
            return

        ok = ctx.db.add_shadow_user(target_uid)
        if ok:
            await message.answer(f"🔒 Пользователь ID <code>{target_uid}</code> добавлен в теневой пул.", parse_mode="HTML")
        else:
            await message.answer(f"Пользователь ID <code>{target_uid}</code> уже находится в теневом пуле.", parse_mode="HTML")

    @router.callback_query(F.data.startswith("sb_del:"))
    async def cb_shadow_del(callback: CallbackQuery) -> None:
        if callback.from_user.id != ctx.admin_id or callback.message.chat.type != "private":
            await callback.answer()
            return
        parts = callback.data.split(":")
        target_uid = int(parts[1])
        ctx.db.remove_shadow_user(target_uid)
        await callback.answer(f"Пользователь {target_uid} удален из теневого пула", show_alert=True)
        text, kb = _build_shadow_list_message()
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            pass

    @router.callback_query(F.data == "sb_ref")
    async def cb_shadow_ref(callback: CallbackQuery) -> None:
        if callback.from_user.id != ctx.admin_id or callback.message.chat.type != "private":
            await callback.answer()
            return
        await callback.answer("Обновлено")
        text, kb = _build_shadow_list_message()
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            pass

    return router