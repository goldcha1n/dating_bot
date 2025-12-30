from __future__ import annotations

import re
from typing import Optional

from models import User


def _norm(text: str) -> str:
    """Normalize user input for fuzzy matching."""
    t = (text or "").strip().lower()
    t = re.sub(r"[\s\t\n\r]+", " ", t)
    return t


def gender_to_code(text: str) -> Optional[str]:
    """Return gender code (M/F) from user input."""
    t = _norm(text)
    if t in {"м", "м.", "муж", "мужчина", "мужской", "парень", "m", "male", "man"}:
        return "M"
    if t in {"ж", "ж.", "жен", "женщина", "женский", "девушка", "f", "female", "woman"}:
        return "F"
    return None


def looking_for_to_code(text: str) -> Optional[str]:
    """Return looking_for code (M/F/A) from user input."""
    t = _norm(text)
    if t in {"м", "муж", "мужчина", "парней", "парня", "парни", "парень", "m", "male", "man"}:
        return "M"
    if t in {"ж", "жен", "женщина", "девушек", "девушка", "девушки", "f", "female", "woman"}:
        return "F"
    if t in {"все", "любой", "любые", "любой пол", "any", "all"}:
        return "A"
    return None


def _gender_human(code: str) -> str:
    return {"M": "М", "F": "Ж"}.get(code, code)


def _looking_for_human(code: str) -> str:
    return {"M": "Парни", "F": "Девушки", "A": "Все"}.get(code, code)


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
