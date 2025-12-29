from __future__ import annotations

import logging

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from models import Base

logger = logging.getLogger(__name__)


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, echo=False)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _ensure_schema(engine: AsyncEngine) -> None:
    """Мини-миграции без Alembic.

    create_all не изменяет существующие таблицы, поэтому при апдейте существующей bot.db
    мы добавляем новые колонки вручную (SQLite).
    """
    try:
        if not str(engine.url).startswith("sqlite"):
            return

        async with engine.begin() as conn:
            res = await conn.exec_driver_sql("PRAGMA table_info(users);")
            cols = [row[1] for row in res.fetchall()]
            if "age" not in cols:
                logger.info("Schema migration: adding users.age")
                await conn.exec_driver_sql("ALTER TABLE users ADD COLUMN age INTEGER NOT NULL DEFAULT 16;")

            if "age_filter_enabled" not in cols:
                logger.info("Schema migration: adding users.age_filter_enabled")
                await conn.exec_driver_sql("ALTER TABLE users ADD COLUMN age_filter_enabled INTEGER NOT NULL DEFAULT 1;")
    except Exception:
        logger.exception("Schema migration failed")


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _ensure_schema(engine)
    logger.info("DB initialized (create_all done)")


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        super().__init__()
        self.sessionmaker = sessionmaker

    async def __call__(self, handler, event: TelegramObject, data: dict):
        async with self.sessionmaker() as session:
            data["session"] = session
            return await handler(event, data)
