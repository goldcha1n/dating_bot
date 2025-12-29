from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from models import Like

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResetResult:
    deleted_likes: int


async def reset_likes_and_skips(session: AsyncSession) -> ResetResult:
    """Сбрасываем историю лайков/скипов (таблица Like).
    Мэтчи (Match) не трогаем.
    """
    cnt = await session.execute(select(func.count(Like.id)))
    total = int(cnt.scalar_one())
    await session.execute(delete(Like))
    await session.commit()
    return ResetResult(deleted_likes=total)


def _get_tz(tz_name: str):
    if ZoneInfo is None:
        return timezone.utc
    try:
        return ZoneInfo(tz_name)
    except Exception:
        logger.warning("Timezone %s not found; fallback to UTC. Install tzdata on Windows.", tz_name)
        return timezone.utc


def _now(tz) -> datetime:
    return datetime.now(tz)


def _next_run_dt(tz, hour: int) -> datetime:
    now = _now(tz)
    run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if run <= now:
        run = run + timedelta(days=1)
    return run


async def daily_reset_loop(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    bot: Bot | None,
    tz_name: str,
    hour: int,
    admins: list[int],
) -> None:
    """Фоновый цикл: каждый день в hour:00 (по tz_name) сбрасываем лайки/скипы."""
    tz = _get_tz(tz_name)
    hour = max(0, min(23, int(hour)))

    while True:
        try:
            next_run = _next_run_dt(tz, hour)
            sleep_seconds = max(1.0, (next_run - _now(tz)).total_seconds())
            logger.info("Daily reset scheduled at %s (%s), sleep %.1fs", next_run.isoformat(), tz_name, sleep_seconds)
            await asyncio.sleep(sleep_seconds)

            async with sessionmaker() as session:
                res = await reset_likes_and_skips(session)

            logger.info("Daily reset done: deleted likes=%s", res.deleted_likes)

            if bot and admins:
                text = f"✅ Ежедневный сброс выполнен. Удалено лайков/скипов: {res.deleted_likes}"
                for admin_id in admins:
                    try:
                        await bot.send_message(chat_id=admin_id, text=text)
                    except Exception:
                        logger.exception("Failed to notify admin %s", admin_id)

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Daily reset loop error")
            await asyncio.sleep(60)
