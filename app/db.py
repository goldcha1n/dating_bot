from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


def create_engine(database_url: str | None = None) -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(database_url or settings.database_url, echo=False, future=True)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def session_scope(sessionmaker: async_sessionmaker[AsyncSession]):
    async with sessionmaker() as session:
        yield session
