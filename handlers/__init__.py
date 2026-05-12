from handlers.admin import get_router as admin_router
from handlers.help import get_router as help_router
from handlers.bets import get_router as bets_router
from handlers.leaderboard import get_router as leaderboard_router
from handlers.participants import get_router as participants_router
from handlers.profile import get_router as profile_router
from handlers.settings import get_router as settings_router
from handlers.sleepy import get_router as sleepy_router
from handlers.start import get_router as start_router


def get_routers(ctx):
    return [
        admin_router(ctx),
        help_router(ctx),
        participants_router(ctx),
        leaderboard_router(ctx),
        settings_router(ctx),
        bets_router(ctx),
        profile_router(ctx),
        sleepy_router(ctx),
        start_router(ctx),
    ]
