def has_user_display_name(
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> bool:
    """Проверяет, есть ли у пользователя хоть какое-то имя или юзернейм (не фоллбек на ID)."""
    return bool(
        (username and str(username).strip())
        or (first_name and str(first_name).strip())
        or (last_name and str(last_name).strip())
    )


def get_user_display_name(
    user_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> str | None:
    """
    Возвращает человекочитаемое отображаемое имя (@username или Имя Фамилия).
    Если данных нет — возвращает None (без фоллбека на ID).
    """
    if username and str(username).strip():
        return f"@{str(username).strip()}"
    name_parts = [str(part).strip() for part in [first_name, last_name] if part and str(part).strip()]
    if name_parts:
        return " ".join(name_parts)
    return None


def format_user_name(
    user_id: int, 
    username: str | None, 
    first_name: str | None, 
    last_name: str | None,
) -> str:
    """Форматирует имя пользователя. При отсутствии данных возвращает 'ID {user_id}'."""
    name = get_user_display_name(user_id, username, first_name, last_name)
    if name is not None:
        return name
    return f"ID {user_id}"


def format_user_label(
    user_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> str:
    """
    Форматирует текст для кнопок:
    'Имя Фамилия (@username)' или 'Имя Фамилия' или '@username' или 'ID {user_id}'
    """
    name_parts = [str(part).strip() for part in [first_name, last_name] if part and str(part).strip()]
    full_name = " ".join(name_parts) if name_parts else None
    clean_username = str(username).strip() if username and str(username).strip() else None

    if full_name and clean_username:
        return f"{full_name} (@{clean_username})"
    if full_name:
        return full_name
    if clean_username:
        return f"@{clean_username}"
    return f"ID {user_id}"


def compute_coef(wins_total: int, config: dict) -> float:
    if wins_total == 0:
        return float(config["bet_coef_new"])
    coef = float(config["bet_coef_max"]) - float(config["bet_coef_decay"]) * max(wins_total - 1, 0)
    coef = max(float(config["bet_coef_min"]), min(coef, float(config["bet_coef_max"])))
    return coef
