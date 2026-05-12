import asyncio
import os
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from handlers import get_routers
from tasks.scheduler import start_scheduler
from utils.config import load_config
from utils.context import AppContext
from utils.storage import Database


async def main() -> None:
    load_dotenv()
    config = load_config()
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set in .env")
    admin_id_raw = os.getenv("ADMIN_ID")
    if not admin_id_raw:
        raise RuntimeError("ADMIN_ID is not set in .env")
    admin_id = int(admin_id_raw)

    tz = ZoneInfo(config["timezone"])
    db = Database(config["db_path"])
    db.init()

    bot = Bot(bot_token)
    ctx = AppContext(config=config, tz=tz, db=db, bot=bot, admin_id=admin_id)

    dp = Dispatcher()
    for router in get_routers(ctx):
        dp.include_router(router)

    await start_scheduler(ctx)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
