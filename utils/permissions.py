from __future__ import annotations

from app.config import Config


def is_admin(cfg: Config, tg_user_id: int) -> bool:
    return tg_user_id in set(cfg.admins or [])
