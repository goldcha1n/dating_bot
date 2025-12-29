from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Like, Match


@dataclass(frozen=True)
class ResetFeedResult:
    deleted_likes: int
    deleted_matches: int


async def reset_feed(session: AsyncSession) -> ResetFeedResult:
    """Сбросить ленту полностью: удалить историю лайков/скипов и мэтчи.

    Анкеты/фото не трогаем.
    """
    likes = int((await session.execute(select(func.count(Like.id)))).scalar_one())
    matches = int((await session.execute(select(func.count(Match.id)))).scalar_one())

    await session.execute(delete(Like))
    await session.execute(delete(Match))
    await session.commit()

    return ResetFeedResult(deleted_likes=likes, deleted_matches=matches)
