
def format_user_name(user_id: int, 
                     username: str | None, 
                     first_name: str | None, 
                     last_name: str | None
                     ) -> str:
    if username:
        return f"@{username}"
    name_parts = [part for part in [first_name, last_name] if part]
    if name_parts:
        return " ".join(name_parts)
    return f"ID {user_id}"


def compute_coef(wins_total: int, config: dict) -> float:
    if wins_total == 0:
        return float(config["bet_coef_new"])
    coef = float(config["bet_coef_max"]) - float(config["bet_coef_decay"]) * max(wins_total - 1, 0)
    coef = max(float(config["bet_coef_min"]), min(coef, float(config["bet_coef_max"])))
    return coef
