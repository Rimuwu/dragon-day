from dataclasses import dataclass
from zoneinfo import ZoneInfo

from aiogram import Bot

from utils.storage import Database


@dataclass
class AppContext:
    config: dict
    tz: ZoneInfo
    db: Database
    bot: Bot
