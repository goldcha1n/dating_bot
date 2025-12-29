from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import load_config
from db import DbSessionMiddleware, create_engine, create_sessionmaker, init_db
from services.daily_reset import daily_reset_loop

from handlers.onboarding import router as onboarding_router
from handlers.profile import router as profile_router
from handlers.browse import router as browse_router
from handlers.matches import router as matches_router
from handlers.settings import router as settings_router
from handlers.admin import router as admin_router
from handlers.common import router as common_router


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    cfg = load_config()

    engine = create_engine(cfg.database_url)
    sessionmaker = create_sessionmaker(engine)
    await init_db(engine)

    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(DbSessionMiddleware(sessionmaker))

    dp.include_router(common_router)
    dp.include_router(onboarding_router)
    dp.include_router(profile_router)
    dp.include_router(browse_router)
    dp.include_router(matches_router)
    dp.include_router(settings_router)
    dp.include_router(admin_router)

    # Ежедневный сброс истории лайков/скипов в 08:00 (Europe/Kyiv).
    # Включается/настраивается через .env: DAILY_RESET_*
    if cfg.reset_enabled:
        asyncio.create_task(
            daily_reset_loop(
                sessionmaker,
                bot=bot,
                tz_name=cfg.reset_timezone,
                hour=cfg.reset_hour,
                admins=cfg.admins,
            )
        )

    await dp.start_polling(bot, cfg=cfg)


if __name__ == "__main__":
    asyncio.run(main())
