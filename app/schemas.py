from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UserOut(BaseModel):
    id: int
    tg_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_banned: bool
    created_at: datetime


class AdminActionOut(BaseModel):
    id: int
    admin_username: str
    action: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    payload_json: Optional[str] = None
    created_at: datetime
