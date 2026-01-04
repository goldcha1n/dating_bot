from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import Settings
from db import BanCheckMiddleware, DbSessionMiddleware, create_engine, create_sessionmaker, init_db
from handlers.admin import router as admin_router
from handlers.browse import router as browse_router
from handlers.common import router as common_router
from handlers.matches import router as matches_router
from handlers.complaints import router as complaints_router
from handlers.onboarding import router as onboarding_router
from handlers.profile import router as profile_router
from handlers.feedback import router as feedback_router
from handlers.settings import router as settings_router
from services.daily_reset import daily_reset_loop

logger = logging.getLogger(__name__)


def _build_dispatcher(sessionmaker):
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(DbSessionMiddleware(sessionmaker))
    ban_mw = BanCheckMiddleware(sessionmaker)
    dp.update.middleware(ban_mw)
    dp.message.middleware(ban_mw)
    dp.callback_query.middleware(ban_mw)

    dp.include_router(common_router)
    dp.include_router(onboarding_router)
    dp.include_router(profile_router)
    dp.include_router(browse_router)
    dp.include_router(matches_router)
    dp.include_router(complaints_router)
    dp.include_router(feedback_router)
    dp.include_router(settings_router)
    dp.include_router(admin_router)
    return dp


async def start_bot(settings: Settings) -> None:
    engine = create_engine(settings.database_url)
    sessionmaker = create_sessionmaker(engine)
    await init_db(engine)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = _build_dispatcher(sessionmaker)

    reset_task = None
    if settings.reset_enabled:
        reset_task = asyncio.create_task(
            daily_reset_loop(
                sessionmaker,
                bot=bot,
                tz_name=settings.reset_timezone,
                hour=settings.reset_hour,
                admins=settings.admins,
            )
        )

    logger.info("bot started")
    try:
        await dp.start_polling(bot, cfg=settings)
    finally:
        if reset_task:
            reset_task.cancel()
            await asyncio.gather(reset_task, return_exceptions=True)
        await bot.session.close()
        await engine.dispose()
