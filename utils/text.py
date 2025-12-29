from __future__ import annotations

import re
from typing import Optional

from models import User


def _norm(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"[\s\t\n\r]+", " ", t)
    return t


def gender_to_code(text: str) -> Optional[str]:
    t = _norm(text)
    if "муж" in t or t in ("м", "male", "man") or "👨" in t:
        return "M"
    if "жен" in t or t in ("ж", "female", "woman") or "👩" in t:
        return "F"
    return None


def looking_for_to_code(text: str) -> Optional[str]:
    t = _norm(text)
    if "муж" in t or "парн" in t or "👨" in t:
        return "M"
    if "жен" in t or "девуш" in t or "👩" in t:
        return "F"
    if "всех" in t or "все" in t or "любой" in t or "🌍" in t:
        return "A"
    return None


def _gender_human(code: str) -> str:
    return {"M": "М", "F": "Ж"}.get(code, code)


def _looking_for_human(code: str) -> str:
    return {"M": "Парней", "F": "Девушек", "A": "Всех"}.get(code, code)


def render_profile_caption(user: User) -> str:
    title = f"<b>{user.name}, {user.age}</b> • {user.city}"
    meta = f"Пол: {_gender_human(user.gender)} • Ищу: {_looking_for_human(user.looking_for)}"
    parts = [title, meta]
    if user.about:
        parts.append("")
        parts.append(f"<i>{user.about}</i>")
    return "\n".join(parts)


def contact_url(user: User) -> str:
    if user.username:
        return f"https://t.me/{user.username}"
    return f"tg://user?id={user.tg_id}"
