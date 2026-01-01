from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot
from sqlalchemy import and_, delete, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from keyboards.inline_profiles import like_notification_kb, match_contact_kb
from models import Like, Match, Photo, User
from utils.text import contact_url, render_profile_caption

logger = logging.getLogger(__name__)


async def get_current_user_or_none(session: AsyncSession, tg_id: int) -> Optional[User]:
    res = await session.execute(
        select(User).options(selectinload(User.photos)).where(User.tg_id == tg_id)
    )
    return res.scalar_one_or_none()


async def _get_user_by_id_with_photos(session: AsyncSession, user_id: int) -> Optional[User]:
    res = await session.execute(
        select(User).options(selectinload(User.photos)).where(User.id == user_id)
    )
    return res.scalar_one_or_none()


def _main_photo_file_id(user: User) -> Optional[str]:
    for p in user.photos:
        if p.is_main:
            return p.file_id
    if user.photos:
        return user.photos[0].file_id
    return None


def _location_filters(current: User) -> list:
    """Повертає SQLAlchemy умови за обраним рівнем пошуку."""
    scope = getattr(current, "search_scope", None)
    allowed = {"settlement", "hromada", "district", "region", "country"}
    search_global = getattr(current, "search_global", False)
    if search_global:
        scope = "country"
    elif scope not in allowed:
        scope = "settlement"

    region = getattr(current, "region", None)
    district = getattr(current, "district", None)
    hromada = getattr(current, "hromada", None)
    settlement = getattr(current, "settlement", None)

    if scope == "country":
        return []

    if scope == "region":
        return [User.region == region] if region else []

    if scope == "hromada":
        filters = []
        if region:
            filters.append(User.region == region)
        if district:
            filters.append(User.district == district)
        if hromada:
            filters.append(User.hromada == hromada)
        return filters

    if scope == "district":
        if region and district:
            return [User.region == region, User.district == district]
        return [User.region == region] if region else []

    # settlement
    filters = []
    if region:
        filters.append(User.region == region)
    if district:
        filters.append(User.district == district)
    if hromada:
        filters.append(User.hromada == hromada)
    if settlement:
        filters.append(User.settlement == settlement)
    return filters


async def get_next_candidate(session: AsyncSession, current: User) -> Optional[User]:
    already_seen = exists(
        select(Like.id).where(and_(Like.from_user_id == current.id, Like.to_user_id == User.id))
    )

    already_matched = exists(
        select(Match.id).where(
            or_(
                and_(Match.user1_id == current.id, Match.user2_id == User.id),
                and_(Match.user2_id == current.id, Match.user1_id == User.id),
            )
        )
    )

    conditions = [
        User.active == True,  # noqa: E712
        User.id != current.id,
        ~already_seen,
        ~already_matched,
    ]

    if current.looking_for in ("M", "F"):
        conditions.append(User.gender == current.looking_for)

    conditions.extend(_location_filters(current))

    # Віковий фільтр: за замовчуванням показуємо анкети від (age-3) до (age+2)
    if getattr(current, "age_filter_enabled", True):
        min_age = max(16, int(current.age) - 3)
        max_age = min(99, int(current.age) + 2)
        conditions.append(User.age.between(min_age, max_age))

    stmt = (
        select(User)
        .options(selectinload(User.photos))
        .where(and_(*conditions))
        .order_by(User.created_at.desc())
    )
    res = await session.execute(stmt)
    return res.scalars().first()


async def _send_like_notification(bot: Bot, from_user: User, to_user: User) -> None:
    """Уведомление: 'вас лайкнули' (без контактов)."""
    try:
        photo_id = _main_photo_file_id(from_user)
        text = (
            "❤️ <b>Вам поставили лайк</b>\n\n"
            f"{render_profile_caption(from_user)}\n\n"
            "Хочете відповісти взаємно?"
        )
        kb = like_notification_kb(from_user.id)

        if photo_id:
            await bot.send_photo(chat_id=to_user.tg_id, photo=photo_id, caption=text, reply_markup=kb)
        else:
            await bot.send_message(chat_id=to_user.tg_id, text=text, reply_markup=kb)
    except Exception:
        logger.exception("Failed to send like notification")


async def _send_match_cards(bot: Bot, u1: User, u2: User) -> None:
    """При мэтче: карточка профілю + кнопка 'Написати'."""
    try:
        kb_2 = match_contact_kb(contact_url(u2), target_user_id=u2.id)
        photo_2 = _main_photo_file_id(u2)
        text_2 = f"🎉 <b>Взаємна симпатія!</b>\n\n{render_profile_caption(u2)}"
        if photo_2:
            await bot.send_photo(chat_id=u1.tg_id, photo=photo_2, caption=text_2, reply_markup=kb_2)
        else:
            await bot.send_message(chat_id=u1.tg_id, text=text_2, reply_markup=kb_2)

        kb_1 = match_contact_kb(contact_url(u1), target_user_id=u1.id)
        photo_1 = _main_photo_file_id(u1)
        text_1 = f"🎉 <b>Взаємна симпатія!</b>\n\n{render_profile_caption(u1)}"
        if photo_1:
            await bot.send_photo(chat_id=u2.tg_id, photo=photo_1, caption=text_1, reply_markup=kb_1)
        else:
            await bot.send_message(chat_id=u2.tg_id, text=text_1, reply_markup=kb_1)
    except Exception:
        logger.exception("Failed to send match notifications")


async def put_reaction_and_maybe_match(
    session: AsyncSession,
    from_user: User,
    to_user_id: int,
    is_like: bool,
    bot: Bot,
) -> tuple[bool, Optional[User]]:
    """Зберігаємо реакцію. При взаємності створюємо Match і повідомляємо обох."""
    if to_user_id == from_user.id:
        return False, None

    to_user = await _get_user_by_id_with_photos(session, to_user_id)
    if not to_user:
        return False, None

    res2 = await session.execute(
        select(Like).where(Like.from_user_id == from_user.id, Like.to_user_id == to_user.id)
    )
    if res2.scalar_one_or_none():
        return False, None

    session.add(Like(from_user_id=from_user.id, to_user_id=to_user.id, is_like=is_like))
    await session.flush()

    if not is_like:
        await session.commit()
        return False, None

    await session.commit()
    await _send_like_notification(bot, from_user=from_user, to_user=to_user)

    res3 = await session.execute(
        select(Like).where(
            Like.from_user_id == to_user.id,
            Like.to_user_id == from_user.id,
            Like.is_like == True,  # noqa: E712
        )
    )
    if not res3.scalar_one_or_none():
        return False, None

    u1_id, u2_id = (from_user.id, to_user.id) if from_user.id < to_user.id else (to_user.id, from_user.id)
    res4 = await session.execute(select(Match).where(Match.user1_id == u1_id, Match.user2_id == u2_id))
    if res4.scalar_one_or_none():
        return False, to_user

    session.add(Match(user1_id=u1_id, user2_id=u2_id))
    await session.commit()

    u1 = await _get_user_by_id_with_photos(session, from_user.id) or from_user
    u2 = await _get_user_by_id_with_photos(session, to_user.id) or to_user
    await _send_match_cards(bot, u1=u1, u2=u2)

    return True, to_user


async def delete_user_account(session: AsyncSession, tg_id: int) -> None:
    user = await get_current_user_or_none(session, tg_id)
    if not user:
        return

    await session.execute(delete(Like).where(or_(Like.from_user_id == user.id, Like.to_user_id == user.id)))
    await session.execute(delete(Match).where(or_(Match.user1_id == user.id, Match.user2_id == user.id)))
    await session.execute(delete(Photo).where(Photo.user_id == user.id))
    await session.execute(delete(User).where(User.id == user.id))
    await session.commit()
