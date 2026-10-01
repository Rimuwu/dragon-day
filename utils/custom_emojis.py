import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import (
    BufferedInputFile,
    InputSticker,
    RichText,
    RichTextCustomEmoji,
)
from PIL import Image
import io

logger = logging.getLogger(__name__)

DATA_FILE = Path("data/custom_emojis.json")
ASSETS_EMOJIS_DIR = Path("assets/emojis")

EMOJI_DEFINITIONS = [
    ("sun", "assets/emojis/sun.png", "☀️"),
    ("evil", "assets/emojis/evil.png", "😈"),
    ("sleepy", "assets/emojis/sleepy.png", "🌙"),
    ("crown", "assets/emojis/crown.png", "👑"),
    ("dice", "assets/emojis/dice.png", "🎲"),
    ("coin", "assets/emojis/coin.png", "🪙"),
    ("fire", "assets/emojis/fire.png", "🔥"),
]

_CACHE: dict[str, str] = {}


def load_custom_emojis() -> dict[str, str]:
    global _CACHE
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                _CACHE = json.load(f)
                return _CACHE
        except Exception as e:
            logger.error("Failed to load %s: %s", DATA_FILE, e)
    return _CACHE


def save_custom_emojis(mapping: dict[str, str]) -> None:
    global _CACHE
    _CACHE = mapping
    try:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        logger.info("Saved custom emojis mapping to %s", DATA_FILE)
    except Exception as e:
        logger.error("Failed to save %s: %s", DATA_FILE, e)


def get_emoji_id(name: str) -> Optional[str]:
    if not _CACHE:
        load_custom_emojis()
    return _CACHE.get(name)


def fmt_emoji(name: str, fallback: str = "") -> str:
    e_id = get_emoji_id(name)
    if e_id:
        return f'<tg-emoji emoji-id="{e_id}">{fallback}</tg-emoji>'
    return fallback


def get_rich_emoji(name: str, fallback: str = "") -> RichTextCustomEmoji | RichText:
    e_id = get_emoji_id(name)
    if e_id:
        return RichTextCustomEmoji(custom_emoji_id=e_id, alternative_text=fallback)
    return RichText(text=fallback)


async def ensure_custom_emojis(bot: Bot, admin_id: int) -> dict[str, str]:
    """
    Checks Telegram custom emoji sticker pack, creates or syncs if needed,
    and returns a mapping of emoji key to custom_emoji_id.
    """
    current_mapping = load_custom_emojis()
    all_present = all(k in current_mapping and current_mapping[k] for k, _, _ in EMOJI_DEFINITIONS)
    if all_present:
        return current_mapping

    try:
        bot_user = await bot.get_me()
        bot_username = bot_user.username.lower()
    except Exception as e:
        logger.error("Failed to get bot info: %s", e)
        return current_mapping

    pack_name = f"dragonday_v2_by_{bot_username}"
    pack_title = "Dragon Day Chibi Emojis"

    sticker_set = None
    try:
        sticker_set = await bot.get_sticker_set(pack_name)
    except TelegramBadRequest as e:
        if "STICKERSET_INVALID" in str(e):
            sticker_set = None
        else:
            logger.warning("Error fetching sticker set %s: %s", pack_name, e)

    if sticker_set is None:
        first_key, first_path, first_char = EMOJI_DEFINITIONS[0]
        if not os.path.exists(first_path):
            logger.warning("Emoji source file not found: %s", first_path)
            return current_mapping

        with Image.open(first_path) as img:
            if img.size != (100, 100):
                img = img.resize((100, 100), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            first_bytes = buf.getvalue()

        st_obj = InputSticker(
            sticker=BufferedInputFile(first_bytes, filename=f"{first_key}.png"),
            format="static",
            emoji_list=[first_char],
        )

        try:
            logger.info("Creating sticker set %s with %s...", pack_name, first_key)
            await bot.create_new_sticker_set(
                user_id=admin_id,
                name=pack_name,
                title=pack_title,
                stickers=[st_obj],
                sticker_type="custom_emoji",
            )
            await asyncio.sleep(1.0)
            sticker_set = await bot.get_sticker_set(pack_name)
        except Exception as e:
            logger.error("Failed to create sticker set %s: %s", pack_name, e)
            return current_mapping

    if sticker_set:
        existing_chars = [st.emoji for st in sticker_set.stickers]
        for key, path, char in EMOJI_DEFINITIONS:
            if char in existing_chars:
                continue
            if not os.path.exists(path):
                continue
            try:
                with Image.open(path) as img:
                    if img.size != (100, 100):
                        img = img.resize((100, 100), Image.Resampling.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    b_data = buf.getvalue()

                st_obj = InputSticker(
                    sticker=BufferedInputFile(b_data, filename=f"{key}.png"),
                    format="static",
                    emoji_list=[char],
                )
                logger.info("Adding sticker %s (%s) to %s...", key, char, pack_name)
                await bot.add_sticker_to_set(
                    user_id=admin_id,
                    name=pack_name,
                    sticker=st_obj,
                )
                await asyncio.sleep(0.5)
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
            except Exception as e:
                logger.warning("Failed to add sticker %s: %s", key, e)

        # Retrieve updated IDs
        try:
            updated_set = await bot.get_sticker_set(pack_name)
            new_mapping = {}
            for st in updated_set.stickers:
                for k, _, char in EMOJI_DEFINITIONS:
                    if char == st.emoji:
                        new_mapping[k] = st.custom_emoji_id
            save_custom_emojis(new_mapping)
            return new_mapping
        except Exception as e:
            logger.error("Failed to retrieve updated sticker set: %s", e)

    return current_mapping
