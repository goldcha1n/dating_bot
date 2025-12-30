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
    """Lightweight migrations for SQLite when Alembic is not used."""

    try:
        if not str(engine.url).startswith("sqlite"):
            return

        async with engine.begin() as conn:
            res = await conn.exec_driver_sql("PRAGMA table_info(users);")
            cols = {row[1] for row in res.fetchall()}

            if "age" not in cols:
                logger.info("Schema migration: adding users.age")
                await conn.exec_driver_sql("ALTER TABLE users ADD COLUMN age INTEGER NOT NULL DEFAULT 16;")

            if "age_filter_enabled" not in cols:
                logger.info("Schema migration: adding users.age_filter_enabled")
                await conn.exec_driver_sql("ALTER TABLE users ADD COLUMN age_filter_enabled INTEGER NOT NULL DEFAULT 1;")

            if "first_name" not in cols:
                logger.info("Schema migration: adding users.first_name")
                await conn.exec_driver_sql("ALTER TABLE users ADD COLUMN first_name VARCHAR(64);")

            if "last_name" not in cols:
                logger.info("Schema migration: adding users.last_name")
                await conn.exec_driver_sql("ALTER TABLE users ADD COLUMN last_name VARCHAR(64);")

            if "is_banned" not in cols:
                logger.info("Schema migration: adding users.is_banned")
                await conn.exec_driver_sql("ALTER TABLE users ADD COLUMN is_banned BOOLEAN NOT NULL DEFAULT 0;")

            res = await conn.exec_driver_sql("PRAGMA index_list(users);")
            indexes = {row[1] for row in res.fetchall()}
            if "ix_users_username" not in indexes:
                logger.info("Schema migration: creating ix_users_username index")
                await conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username);")
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
