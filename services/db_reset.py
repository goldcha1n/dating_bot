from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ActionLog, Feedback, Like, Match, Photo, User


@dataclass(frozen=True)
class DbResetResult:
    users: int
    photos: int
    feedback: int
    likes: int
    matches: int
    action_logs: int


async def reset_database(session: AsyncSession) -> DbResetResult:
    """Полный сброс данных бота (анкеты/фото/лайки/мэтчи/логи антифлуда).

    Таблицы и схема остаются. Удаляем только данные.
    """
    users = int((await session.execute(select(func.count(User.id)))).scalar_one())
    photos = int((await session.execute(select(func.count(Photo.id)))).scalar_one())
    feedback = int((await session.execute(select(func.count(Feedback.id)))).scalar_one())
    likes = int((await session.execute(select(func.count(Like.id)))).scalar_one())
    matches = int((await session.execute(select(func.count(Match.id)))).scalar_one())
    logs = int((await session.execute(select(func.count(ActionLog.id)))).scalar_one())

    # Порядок важен из-за внешних ключей
    await session.execute(delete(ActionLog))
    await session.execute(delete(Feedback))
    await session.execute(delete(Like))
    await session.execute(delete(Match))
    await session.execute(delete(Photo))
    await session.execute(delete(User))
    await session.commit()

    return DbResetResult(
        users=users,
        photos=photos,
        feedback=feedback,
        likes=likes,
        matches=matches,
        action_logs=logs,
    )
