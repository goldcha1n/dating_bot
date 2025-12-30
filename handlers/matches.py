from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from keyboards.inline_profiles import matches_pager_kb
from keyboards.main_menu import BTN_MATCHES
from models import Match, User
from services.matching import get_current_user_or_none
from utils.text import contact_url, render_profile_caption

logger = logging.getLogger(__name__)
router = Router()


async def _get_match_other_ids(session: AsyncSession, current_user_id: int) -> list[int]:
    res = await session.execute(
        select(Match)
        .where(or_(Match.user1_id == current_user_id, Match.user2_id == current_user_id))
        .order_by(Match.created_at.desc())
    )
    matches = res.scalars().all()
    other_ids: list[int] = []
    for m in matches:
        other_ids.append(m.user2_id if m.user1_id == current_user_id else m.user1_id)
    return other_ids


async def _render_match_page(session: AsyncSession, other_ids: list[int], page: int) -> tuple[User, str, str, int, int]:
    total = len(other_ids)
    page = max(1, min(page, total))
    other_id = other_ids[page - 1]

    res = await session.execute(
        select(User).options(selectinload(User.photos)).where(User.id == other_id)
    )
    other = res.scalar_one()

    photo_id = None
    for p in other.photos:
        if p.is_main:
            photo_id = p.file_id
            break
    if not photo_id and other.photos:
        photo_id = other.photos[0].file_id

    caption = (
        f"<b>💞 Взаимная симпатия</b>\n\n"
        f"{render_profile_caption(other)}"
    )

    return other, photo_id or "", caption, page, total


async def _send_or_edit_match_card(call: CallbackQuery, photo_id: str, caption: str, kb) -> None:
    """Пытаемся редактировать текущее сообщение. Если не получилось — отправляем новое."""
    try:
        media = InputMediaPhoto(media=photo_id, caption=caption)
        await call.message.edit_media(media=media, reply_markup=kb)
    except Exception:
        logger.exception("Failed to edit match card, fallback to send")
        await call.message.answer_photo(photo=photo_id, caption=caption, reply_markup=kb)


@router.message(F.text.in_({BTN_MATCHES, "Взаимные лайки"}))
async def show_matches(message: Message, session: AsyncSession) -> None:
    cur = await get_current_user_or_none(session, message.from_user.id)
    if not cur:
        await message.answer("Сначала создайте анкету: /start")
        return

    other_ids = await _get_match_other_ids(session, cur.id)
    if not other_ids:
        await message.answer("Пока нет взаимных лайков.")
        return

    other, photo_id, caption, page, total = await _render_match_page(session, other_ids, page=1)
    kb = matches_pager_kb(url=contact_url(other), target_user_id=other.id, page=page, total=total)

    await message.answer_photo(photo=photo_id, caption=caption, reply_markup=kb)


@router.callback_query(F.data.startswith("matches:page:"))
async def matches_pager(call: CallbackQuery, session: AsyncSession) -> None:
    await call.answer()
    cur = await get_current_user_or_none(session, call.from_user.id)
    if not cur:
        await call.message.answer("Сначала создайте анкету: /start")
        return

    other_ids = await _get_match_other_ids(session, cur.id)
    if not other_ids:
        await call.message.answer("Пока нет взаимных лайков.")
        return

    try:
        page = int(call.data.split(":")[-1])
    except Exception:
        page = 1

    other, photo_id, caption, page, total = await _render_match_page(session, other_ids, page=page)
    kb = matches_pager_kb(url=contact_url(other), target_user_id=other.id, page=page, total=total)

    await _send_or_edit_match_card(call, photo_id=photo_id, caption=caption, kb=kb)
