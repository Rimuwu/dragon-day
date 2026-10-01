import asyncio
import logging
import os
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

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

    bot = Bot(bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    ctx = AppContext(config=config, tz=tz, db=db, bot=bot, admin_id=admin_id)

    dp = Dispatcher()
    from utils.effects import DragonEffectsMiddleware
    from utils.guards import TopicCommandsMiddleware
    dp.message.outer_middleware(DragonEffectsMiddleware(ctx))
    dp.message.outer_middleware(TopicCommandsMiddleware(ctx))
    dp.callback_query.outer_middleware(TopicCommandsMiddleware(ctx))
    for router in get_routers(ctx):
        dp.include_router(router)

    await start_scheduler(ctx)
    try:
        from utils.custom_emojis import ensure_custom_emojis
        await ensure_custom_emojis(bot, ctx.admin_id)
    except Exception:
        pass

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
