from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def build_leaderboard_keyboard(
    group_id: int,
    owner_id: int,
    kind: str,
    page: int,
    total: int,
    page_size: int,
) -> InlineKeyboardMarkup:
    total_pages = max(1, (total + page_size - 1) // page_size)
    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.add(
            InlineKeyboardButton(
                text="Назад",
                callback_data=f"lb:{group_id}:{owner_id}:{kind}:{page - 1}",
            )
        )
    if page + 1 < total_pages:
        builder.add(
            InlineKeyboardButton(
                text="Вперед",
                callback_data=f"lb:{group_id}:{owner_id}:{kind}:{page + 1}",
            )
        )
    return builder.as_markup()


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
        name = person.get("username")
        label = f"@{name}" if name else person.get("first_name") or person.get("last_name") or f"ID {person['user_id']}"
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
                text="Вперед",
                callback_data=f"betpage:{group_id}:{owner_id}:{bet_type}:{page + 1}",
            )
        )
    if nav:
        builder.row(*nav)
    return builder.as_markup()
