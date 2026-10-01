from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.helpers import format_user_label


from utils.custom_emojis import get_emoji_id


def build_leaderboard_keyboard(
    group_id: int,
    owner_id: int,
    kind: str,
    page: int,
    total: int,
    page_size: int,
) -> InlineKeyboardMarkup:
    total_pages = max(1, (total + page_size - 1) // page_size)
    categories = [
        ("points", "Очки", "coin", "🪙"),
        ("day", "День", "sun", "☀️"),
        ("evil", "Зло", "evil", "😈"),
        ("sleepy", "Сон", "sleepy", "😴"),
    ]
    tab_row = []
    for c_kind, label, emoji_key, fallback_emoji in categories:
        e_id = get_emoji_id(emoji_key)
        display_label = label if e_id else f"{fallback_emoji} {label}"
        btn_text = f"• {display_label} •" if c_kind == kind else display_label
        tab_row.append(
            InlineKeyboardButton(
                text=btn_text,
                icon_custom_emoji_id=e_id,
                callback_data=f"lb:{group_id}:{owner_id}:{c_kind}:0",
            )
        )

    nav_row = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"lb:{group_id}:{owner_id}:{kind}:{page - 1}",
            )
        )
    if page + 1 < total_pages:
        nav_row.append(
            InlineKeyboardButton(
                text="Вперёд ➡️",
                callback_data=f"lb:{group_id}:{owner_id}:{kind}:{page + 1}",
            )
        )

    keyboard = [tab_row]
    if nav_row:
        keyboard.append(nav_row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_bet_keyboard(
    group_id: int,
    owner_id: int,
    bet_type: str,
    participants: list[dict],
    page: int,
    total: int,
    page_size: int,
    step: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for person in participants:
        label = format_user_label(
            person["user_id"],
            person.get("username"),
            person.get("first_name"),
            person.get("last_name"),
        )
        builder.row(
            InlineKeyboardButton(
                text=f"-{step} {label}",
                callback_data=f"bet:{group_id}:{owner_id}:{bet_type}:{person['user_id']}:-{step}:{page}",
            ),
            InlineKeyboardButton(
                text=f"+{step} {label}",
                callback_data=f"bet:{group_id}:{owner_id}:{bet_type}:{person['user_id']}:{step}:{page}",
            ),
        )

    total_pages = max(1, (total + page_size - 1) // page_size)
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
        builder.row(*nav)
    return builder.as_markup()


def build_sleep_keyboard(group_id: int, sleep_date: str, count: int = 0) -> InlineKeyboardMarkup:
    sleepy_emoji_id = get_emoji_id("sleepy")
    btn_text = f"Участвовать ({count})" if sleepy_emoji_id else f"💤 Участвовать ({count})"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=btn_text,
                    icon_custom_emoji_id=sleepy_emoji_id,
                    callback_data=f"sleepjoin:{group_id}:{sleep_date}",
                )
            ]
        ]
    )
