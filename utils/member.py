from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter

from utils.context import AppContext


async def pick_valid_member(ctx: AppContext, group_id: int, candidates: list[dict]) -> dict | None:
    """Выбирает валидного участника из кандидатов. Удаляет невалидных из БД."""
    if not candidates:
        return None
    
    import random
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
