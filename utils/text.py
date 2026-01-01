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
    """Return gender code (M/F) from user input (UA/RU/EN)."""
    t = _norm(text)
    if t in {"ч", "ч.", "чол", "чоловік", "м", "м.", "муж", "мужчина", "мужской", "хлопець", "парень", "m", "male", "man"}:
        return "M"
    if t in {"ж", "ж.", "жін", "жінка", "жен", "женщина", "женский", "дівчина", "девушка", "f", "female", "woman"}:
        return "F"
    return None


def looking_for_to_code(text: str) -> Optional[str]:
    """Return looking_for code (M/F/A) from user input (UA/RU/EN)."""
    t = _norm(text)
    if t in {"ч", "чол", "чоловік", "хлопець", "хлопця", "хлопці", "парень", "парня", "парни", "m", "male", "man"}:
        return "M"
    if t in {"ж", "жін", "жінка", "дівчина", "дівчата", "дівчат", "девушка", "девушки", "f", "female", "woman"}:
        return "F"
    if t in {"усі", "всі", "будь-хто", "будь який", "будь-який", "будь-яка стать", "any", "all"}:
        return "A"
    return None


def _gender_human(code: str) -> str:
    return {"M": "М", "F": "Ж"}.get(code, code)


def _looking_for_human(code: str) -> str:
    return {"M": "Хлопці", "F": "Дівчата", "A": "Усі"}.get(code, code)


def format_location(user: User) -> str:
    settlement = getattr(user, "settlement", None) or getattr(user, "city", "")
    district = getattr(user, "district", None)
    hromada = getattr(user, "hromada", None)
    region = getattr(user, "region", None)
    settlement_type = getattr(user, "settlement_type", "city")

    parts = []
    if settlement:
        prefix = "с." if settlement_type == "village" else "м."
        parts.append(f"{prefix} {settlement}")
    if hromada:
        parts.append(hromada)
    if district:
        parts.append(district)
    if region:
        parts.append(region)
    if not parts and getattr(user, "city", None):
        parts.append(user.city)
    return ", ".join(parts) if parts else "—"


def render_profile_caption(user: User) -> str:
    title = f"<b>{user.name}, {user.age}</b> • {format_location(user)}"
    meta = f"Стать: {_gender_human(user.gender)} • Шукаю: {_looking_for_human(user.looking_for)}"
    parts = [title, meta]
    if user.about:
        parts.append("")
        parts.append(f"<i>{user.about}</i>")
    return "\n".join(parts)


def contact_url(user: User) -> str:
    if user.username:
        return f"https://t.me/{user.username}"
    return f"tg://user?id={user.tg_id}"
