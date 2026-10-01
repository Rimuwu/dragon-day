import html

from utils.context import AppContext
from utils.helpers import format_leaderboard_user_name, format_user_name
from utils.phrases import pick_phrase


async def build_dragon_caption(
    ctx: AppContext,
    group_id: int,
    winner: dict,
    bet_type: str,
    points: int,
    bets_result: dict | None = None,
    effect: dict | None = None,
) -> str:
    """
    Генерирует текст к фото дракона (день/ночь/злой).
    
    Args:
        ctx: контекст приложения
        group_id: ID группы
        winner: dict с user_id, username, first_name, last_name
        bet_type: "day", "evil", "sleepy"
        points: количество очков
        bets_result: результат settle_bets с won_points, lost_points, winning_bets
    """
    raw_winner_name = format_user_name(
        winner["user_id"],
        winner.get("username"),
        winner.get("first_name"),
        winner.get("last_name"),
    )
    winner_name = html.escape(raw_winner_name)
    
    titles = {
        "day": "Дракон дня",
        "evil": "Злой дракон",
        "sleepy": "Сонный дракон",
    }
    title = titles.get(bet_type, "Дракон")
    
    points_sign = f"+{points}" if points > 0 else str(points)
    caption = f"<b>{title}:</b> {winner_name}\n{points_sign} очков"
    
    if bets_result:
        won_points = bets_result.get("won_points", 0)
        lost_points = bets_result.get("lost_points", 0)
        winners = bets_result.get("winning_bets", [])
        lines = [f"\nСтавки: +{won_points} / -{lost_points}"]
        
        if winners:
            lines.append("Первые 5 сыгравших:")
            for bet in winners:
                bettor = ctx.db.get_user_identity(group_id, bet["user_id"]) or {
                    "user_id": bet["user_id"],
                    "username": None,
                    "first_name": None,
                    "last_name": None,
                }
                raw_bettor_name = format_leaderboard_user_name(
                    bettor["user_id"],
                    bettor.get("username"),
                    bettor.get("first_name"),
                    bettor.get("last_name"),
                )
                bettor_name = html.escape(raw_bettor_name)
                lines.append(f"- {bettor_name}: {bet['amount']} -> {bet['payout']}")
        
        caption = f"{caption}\n" + "\n".join(lines)
    
    phrase = pick_phrase(bet_type)
    if phrase:
        caption = f"{caption}\n\n{phrase}"

    if effect:
        from utils.effects import format_effect_announcement
        caption = f"{caption}{format_effect_announcement(effect)}"

    return caption
