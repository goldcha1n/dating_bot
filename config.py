from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    database_url: str
    admins: List[int]

    about_min_len: int = 10
    max_photos: int = 3

    # Антифлуд/лимиты
    like_limit_per_hour: int = 20          # сколько лайков можно поставить за 60 минут
    view_limit_per_min: int = 40           # сколько показов анкет за минуту
    action_limit_per_min: int = 60         # сколько действий за минуту (лайк/скип/ответы)

    # Ежедневный сброс истории лайков/скипов (чтобы анкеты показывались заново)
    reset_enabled: bool = True
    reset_hour: int = 8                    # 08:00 по Europe/Kyiv
    reset_timezone: str = "Europe/Kyiv"


def _parse_admins(raw: str) -> List[int]:
    raw = (raw or "").strip()
    if not raw:
        return []
    items = [x.strip() for x in raw.split(",") if x.strip()]
    out: List[int] = []
    for it in items:
        try:
            out.append(int(it))
        except ValueError:
            continue
    return out


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    v = raw.strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    return default


def load_config() -> Config:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required in .env")

    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot.db").strip()
    admins = _parse_admins(os.getenv("ADMINS", ""))

    about_min_len = int(os.getenv("ABOUT_MIN_LEN", "10"))
    max_photos = int(os.getenv("MAX_PHOTOS", "3"))

    like_limit_per_hour = int(os.getenv("LIKE_LIMIT_PER_HOUR", "20"))
    view_limit_per_min = int(os.getenv("VIEW_LIMIT_PER_MIN", "40"))
    action_limit_per_min = int(os.getenv("ACTION_LIMIT_PER_MIN", "60"))

    reset_enabled = _parse_bool(os.getenv("DAILY_RESET_ENABLED"), True)
    reset_hour = int(os.getenv("DAILY_RESET_HOUR", "8"))
    reset_timezone = os.getenv("DAILY_RESET_TZ", "Europe/Kyiv").strip() or "Europe/Kyiv"

    return Config(
        bot_token=bot_token,
        database_url=database_url,
        admins=admins,
        about_min_len=about_min_len,
        max_photos=max_photos,
        like_limit_per_hour=like_limit_per_hour,
        view_limit_per_min=view_limit_per_min,
        action_limit_per_min=action_limit_per_min,
        reset_enabled=reset_enabled,
        reset_hour=reset_hour,
        reset_timezone=reset_timezone,
    )
