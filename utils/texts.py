import html

from utils.custom_emojis import fmt_emoji
from utils.helpers import format_leaderboard_user_name, format_user_name


def bet_title(bet_type: str) -> str:
    return "дракона дня" if bet_type == "day" else "злого дракона"


def build_leaderboard_text(kind: str, entries: list[dict], page: int, total: int, page_size: int) -> str:
    category_meta = {
        "points": ("ТАБЛИЦА ЛИДЕРОВ: ОЧКИ", "coin", "🪙", "очков"),
        "day": ("ЗАЛ СЛАВЫ: ДРАКОНЫ ДНЯ", "sun", "☀️", "побед"),
        "evil": ("ЗАЛ СЛАВЫ: ЗЛЫЕ ДРАКОНЫ", "evil", "😈", "побед"),
        "sleepy": ("ЗАЛ СЛАВЫ: СОННЫЕ ДРАКОНЫ", "sleepy", "🌙", "побед"),
    }
    title, icon_key, def_icon, unit = category_meta.get(kind, ("ТАБЛИЦА ЛИДЕРОВ", "crown", "👑", "очков"))
    e_icon = fmt_emoji(icon_key, def_icon)
    coin_e = fmt_emoji("coin", "🪙")
    crown_e = fmt_emoji("crown", "👑")

    if total == 0:
        return f"{e_icon} <b>{title}</b>\n\n<i>В этой группе пока нет данных рейтинга.</i>"

    start_index = page * page_size + 1
    total_pages = max(1, (total + page_size - 1) // page_size)

    lines = [
        f"{e_icon} <b>{title}</b>",
        f"<i>Страница {page + 1} из {total_pages} (всего {total} участников)</i>",
        "────────────────────",
    ]

    for idx, entry in enumerate(entries, start=start_index):
        name = html.escape(
            format_leaderboard_user_name(
                entry["user_id"],
                entry.get("username"),
                entry.get("first_name"),
                entry.get("last_name"),
            )
        )
        if kind == "points":
            val_formatted = f"{entry['points']:,} {coin_e}".replace(",", " ")
        else:
            wins = entry["wins_day"] if kind == "day" else (entry["wins_evil"] if kind == "evil" else entry["wins_sleepy"])
            val_formatted = f"{wins} {crown_e}"

        if idx == 1:
            rank_badge = "🥇"
        elif idx == 2:
            rank_badge = "🥈"
        elif idx == 3:
            rank_badge = "🥉"
        else:
            rank_badge = f"<b>{idx}.</b>"

        lines.append(f"{rank_badge} {name} — {val_formatted}")

    lines.append("────────────────────")
    return "\n".join(lines)


def build_bet_text(
    bet_type: str,
    points: int,
    participants: list[dict],
    amounts: dict[int, int],
    page: int,
    total: int,
    page_size: int,
    step: int,
) -> str:
    title = f"Ставка на {bet_title(bet_type)}"
    if total == 0:
        return f"{title}\n\nПока нет участников."
    lines = [title, f"Ваши очки: {points}", "", "Участники:"]
    start_index = page * page_size + 1
    for idx, person in enumerate(participants, start=start_index):
        name = format_user_name(
            person["user_id"],
            person.get("username"),
            person.get("first_name"),
            person.get("last_name"),
        )
        amount = amounts.get(person["user_id"], 0)
        lines.append(f"{idx}. {name} — ставка: {amount}")
    total_pages = max(1, (total + page_size - 1) // page_size)
    lines.append("")
    lines.append(f"Страница {page + 1} / {total_pages}")
    lines.append(f"Шаг ставки: {step} очков.")
    return "\n".join(lines)
