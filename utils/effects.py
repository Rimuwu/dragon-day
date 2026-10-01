import random
from utils.context import AppContext

DAY_DRAGON_EFFECTS = [
    {
        "key": "crown",
        "name": "Королевская корона",
        "emoji": "👑",
        "description": "Бот весь день приветствует короля короной 👑 на каждое сообщение в группе.",
    },
    {
        "key": "lightning",
        "name": "Молния величия",
        "emoji": "⚡",
        "description": "Бот озаряет каждое сообщение дракона дня молнией ⚡.",
    },
    {
        "key": "triumph",
        "name": "Триумф стаи",
        "emoji": "🎉",
        "description": "Праздничный салют 🎉 сопровождает каждое послание победителя.",
    },
]

EVIL_DRAGON_EFFECTS = [
    {
        "key": "demon",
        "name": "Демоническая метка",
        "emoji": "😈",
        "description": "Печать темных сил 😈 ставится на каждое сообщение злого дракона.",
    },
    {
        "key": "flame",
        "name": "Инфернальное пламя",
        "emoji": "🔥",
        "description": "Огонь преисподней 🔥 сжигает каждое сообщение темного лорда.",
    },
    {
        "key": "clown",
        "name": "Печать безумия",
        "emoji": "🤡",
        "description": "Клеймо хаоса 🤡 венчает каждое сообщение сеющего безумие.",
    },
]


def pick_random_effect(dragon_type: str) -> dict:
    pool = DAY_DRAGON_EFFECTS if dragon_type == "day" else EVIL_DRAGON_EFFECTS
    return random.choice(pool)


def apply_dragon_effect(
    ctx: AppContext,
    group_id: int,
    dragon_type: str,
    user_id: int,
    effect_date: str,
) -> dict:
    effect = pick_random_effect(dragon_type)
    ctx.db.save_dragon_effect(
        group_id=group_id,
        dragon_type=dragon_type,
        effect_date=effect_date,
        user_id=user_id,
        effect_key=effect["key"],
        effect_emoji=effect["emoji"],
        effect_name=effect["name"],
    )
    return effect


def format_effect_announcement(effect: dict) -> str:
    name = effect.get("name") or effect.get("effect_name", "Эффект")
    emoji = effect.get("emoji") or effect.get("effect_emoji", "✨")
    return (
        f"\n\n✨ <b>Эффект дня: {name}</b> {emoji}\n"
        f"<i>Бот весь день будет ставить реакцию {emoji} на каждое сообщение победителя в чате!</i>"
    )


from aiogram import BaseMiddleware
from aiogram.types import Message, ReactionTypeEmoji
from typing import Callable, Dict, Any, Awaitable
from utils.time_utils import today_str


class DragonEffectsMiddleware(BaseMiddleware):
    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.chat and event.chat.id < 0 and event.from_user and not event.from_user.is_bot:
            try:
                today = today_str(self.ctx.tz)
                effect = self.ctx.db.get_active_dragon_effect_for_user(
                    group_id=event.chat.id,
                    user_id=event.from_user.id,
                    effect_date=today,
                )
                if effect and effect.get("effect_emoji"):
                    try:
                        await event.react([ReactionTypeEmoji(emoji=effect["effect_emoji"])])
                    except Exception:
                        pass
            except Exception:
                pass
        return await handler(event, data)
