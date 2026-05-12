from utils.helpers import format_user_name


def bet_title(bet_type: str) -> str:
    return "дракона дня" if bet_type == "day" else "злого дракона"


def build_leaderboard_text(kind: str, entries: list[dict], page: int, total: int, page_size: int) -> str:
    title = {
        "points": "Топ по очкам",
        "day": "Топ драконов дня",
        "evil": "Топ злых драконов",
        "sleepy": "Топ сонных драконов",
    }[kind]
    if total == 0:
        return f"{title}\n\nПока нет данных."
    start_index = page * page_size + 1
    lines = [title, ""]
    for idx, entry in enumerate(entries, start=start_index):
        name = format_user_name(
            entry["user_id"],
            None,
            entry.get("first_name"),
            entry.get("last_name"),
        )
        if kind == "points":
            value = entry["points"]
        elif kind == "day":
            value = entry["wins_day"]
        elif kind == "evil":
            value = entry["wins_evil"]
        else:
            value = entry["wins_sleepy"]
        lines.append(f"{idx}. {name} — {value}")
    total_pages = max(1, (total + page_size - 1) // page_size)
    lines.append("")
    lines.append(f"Страница {page + 1} / {total_pages}")
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
            None,
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
