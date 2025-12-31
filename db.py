from __future__ import annotations

import logging
from typing import Optional

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from models import Base, User

logger = logging.getLogger(__name__)


def create_engine(database_url: Optional[str]) -> AsyncEngine:
    return create_async_engine(database_url or "", echo=False)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("DB initialized (create_all done)")


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        super().__init__()
        self.sessionmaker = sessionmaker

    async def __call__(self, handler, event: TelegramObject, data: dict):
        async with self.sessionmaker() as session:
            data["session"] = session
            return await handler(event, data)


class BanCheckMiddleware(BaseMiddleware):
    """Skip processing updates from banned users."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        super().__init__()
        self.sessionmaker = sessionmaker

    async def __call__(self, handler, event: TelegramObject, data: dict):
        from_user = getattr(event, "from_user", None)
        if from_user is None:
            return await handler(event, data)

        session: Optional[AsyncSession] = data.get("session")
        created_here = False
        if session is None:
            session = self.sessionmaker()
            created_here = True

        try:
            res = await session.execute(select(User).where(User.tg_id == from_user.id))
            user = res.scalar_one_or_none()
            if user is None:
                return await handler(event, data)

            if getattr(user, "is_banned", False):
                logger.info("Ignore update from banned user tg_id=%s", from_user.id)
                return None

            data.setdefault("user", user)
            return await handler(event, data)
        except Exception:
            logger.exception("Ban check failed (db error)")
            return await handler(event, data)
        finally:
            if created_here:
                await session.close()
