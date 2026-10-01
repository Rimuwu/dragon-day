import secrets
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter

from utils.context import AppContext
from utils.helpers import has_user_display_name


async def resolve_user_display(
    ctx: AppContext,
    group_id: int,
    user_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """
    Проверяет наличие имени пользователя. Если имя отсутствует,
    пытается получить данные участника из Telegram и обновить БД.
    Возвращает (username, first_name, last_name) или (None, None, None) при неудаче.
    """
    if has_user_display_name(username, first_name, last_name):
        return username, first_name, last_name

    try:
        member = await ctx.bot.get_chat_member(group_id, user_id)
        if member and member.user and member.status not in ("left", "kicked"):
            u = member.user
            ctx.db.sync_user(group_id, user_id, u.username, u.first_name, u.last_name)
            return u.username, u.first_name, u.last_name
    except (TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter, Exception):
        pass

    return None, None, None


async def pick_valid_member(
    ctx: AppContext,
    group_id: int,
    candidates: list[dict],
    bet_type: str = "day",
) -> dict | None:
    """
    Выбирает валидного участника с использованием криптографической случайности (secrets.SystemRandom)
    и динамического взвешивания для гарантированного и равномерного охвата всех пользователей.
    Участники с меньшим числом побед получают значительно больший вес.
    Удаляет невалидных пользователей из БД.
    """
    if not candidates:
        return None

    rng = secrets.SystemRandom()
    remaining = candidates[:]

    shadow_ids = ctx.db.get_shadow_user_ids()
    if shadow_ids and rng.random() < 0.99:
        clean_candidates = [p for p in remaining if p["user_id"] not in shadow_ids]
        if clean_candidates:
            remaining = clean_candidates

    # Загружаем статистику для вычисления справедливых весов охвата
    scores: dict[int, int] = {}
    for person in remaining:
        uid = person["user_id"]
        stats = ctx.db.get_user_stats(group_id, uid) or {}
        cat_wins = stats.get(f"wins_{bet_type}", 0)
        total_wins = (
            stats.get("wins_day", 0)
            + stats.get("wins_evil", 0)
            + stats.get("wins_sleepy", 0)
        )
        scores[uid] = 3 * cat_wins + total_wins

    while remaining:
        max_score = max(scores[p["user_id"]] for p in remaining)
        # Вес: чем меньше побед, тем выше вероятность выбора. Вес всегда >= 1.
        weights = [max_score - scores[p["user_id"]] + 1 for p in remaining]

        chosen = rng.choices(remaining, weights=weights, k=1)[0]

        try:
            member = await ctx.bot.get_chat_member(group_id, chosen["user_id"])
        except TelegramBadRequest as e:
            msg = str(e)
            if "PARTICIPANT_ID_INVALID" in msg or "USER_ID_INVALID" in msg or "user not found" in msg.lower():
                try:
                    ctx.db.remove_participant(group_id, chosen["user_id"])
                except Exception:
                    pass
                remaining.remove(chosen)
                continue
            else:
                remaining.remove(chosen)
                continue
        except (TelegramNetworkError, TelegramRetryAfter, Exception):
            remaining.remove(chosen)
            continue

        if member.status not in ("left", "kicked"):
            # Обновляем профиль пользователя в БД, если имя отсутствовало
            if member.user and not has_user_display_name(chosen.get("username"), chosen.get("first_name"), chosen.get("last_name")):
                chosen["username"] = member.user.username
                chosen["first_name"] = member.user.first_name
                chosen["last_name"] = member.user.last_name
                ctx.db.sync_user(group_id, chosen["user_id"], member.user.username, member.user.first_name, member.user.last_name)
            return chosen

        remaining.remove(chosen)

    return None
