from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ActionLog


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def count_actions(
    session: AsyncSession,
    user_id: int,
    actions: Iterable[str],
    window_seconds: int,
) -> int:
    since = _utcnow() - timedelta(seconds=window_seconds)
    stmt = (
        select(func.count(ActionLog.id))
        .where(
            ActionLog.user_id == user_id,
            ActionLog.action.in_(list(actions)),
            ActionLog.created_at >= since,
        )
    )
    return int((await session.execute(stmt)).scalar_one())


async def is_allowed(
    session: AsyncSession,
    user_id: int,
    actions: Iterable[str],
    limit: int,
    window_seconds: int,
) -> bool:
    if limit <= 0:
        return True
    cnt = await count_actions(session, user_id=user_id, actions=actions, window_seconds=window_seconds)
    return cnt < limit


async def log_action(session: AsyncSession, user_id: int, action: str) -> None:
    session.add(ActionLog(user_id=user_id, action=action))
    # Простая уборка: удаляем логи старше 3 суток, чтобы таблица не пухла.
    cutoff = _utcnow() - timedelta(days=3)
    await session.execute(delete(ActionLog).where(ActionLog.created_at < cutoff))
