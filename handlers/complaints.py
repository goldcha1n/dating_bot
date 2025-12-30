from __future__ import annotations

import logging
from typing import Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.inline_profiles import complaint_reasons_kb
from models import Complaint, User
from services.matching import get_current_user_or_none

logger = logging.getLogger(__name__)
router = Router()


class ComplaintStates(StatesGroup):
    waiting_reason_text = State()


async def _get_target(session: AsyncSession, target_user_id: int) -> Optional[User]:
    res = await session.execute(select(User).where(User.id == target_user_id))
    return res.scalar_one_or_none()


async def _create_complaint(
    session: AsyncSession, reporter_id: int, target_user_id: int, reason: str
) -> tuple[bool, str]:
    existing = await session.execute(
        select(Complaint).where(
            Complaint.reporter_user_id == reporter_id, Complaint.target_user_id == target_user_id
        )
    )
    if existing.scalar_one_or_none():
        return False, "Ви вже скаржилися на цю анкету."

    session.add(
        Complaint(
            reporter_user_id=reporter_id,
            target_user_id=target_user_id,
            reason=reason.strip() or "Без причини",
        )
    )
    try:
        await session.commit()
        return True, "Скаргу відправлено."
    except IntegrityError:
        await session.rollback()
        return False, "Ви вже скаржилися на цю анкету."
    except Exception:
        await session.rollback()
        logger.exception("Failed to save complaint")
        return False, "Не вдалося зберегти скаргу. Спробуйте пізніше."


@router.callback_query(F.data.startswith("complaint:start:"))
async def complaint_start(call: CallbackQuery, session: AsyncSession) -> None:
    await call.answer()
    cur = await get_current_user_or_none(session, call.from_user.id)
    if not cur:
        await call.message.answer("Спочатку заповніть профіль: /start")
        return

    try:
        target_user_id = int(call.data.split(":")[-1])
    except Exception:
        await call.message.answer("Некоректна скарга.")
        return

    target = await _get_target(session, target_user_id)
    if not target:
        await call.message.answer("Анкета не знайдена.")
        return

    kb = complaint_reasons_kb(target_user_id)
    await call.message.answer("Оберіть причину скарги:", reply_markup=kb)


@router.callback_query(F.data.startswith("complaint:reason:"))
async def complaint_reason(call: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await call.answer()
    cur = await get_current_user_or_none(session, call.from_user.id)
    if not cur:
        await call.message.answer("Спочатку заповніть профіль: /start")
        return

    try:
        _, _, code, target_raw = call.data.split(":", 3)
        target_user_id = int(target_raw)
    except Exception:
        await call.message.answer("Некоректна скарга.")
        return

    if code == "other":
        await state.update_data(target_user_id=target_user_id)
        await state.set_state(ComplaintStates.waiting_reason_text)
        await call.message.answer("Опишіть причину скарги одним повідомленням:")
        return

    reason_map = {
        "spam": "Спам/реклама",
        "fake": "Фейкова анкета",
        "obscene": "Непристойний контент",
        "other": "Інше",
    }
    reason_text = reason_map.get(code, code)
    ok, msg = await _create_complaint(session, reporter_id=cur.id, target_user_id=target_user_id, reason=reason_text)
    await call.message.answer(msg)


@router.message(ComplaintStates.waiting_reason_text)
async def complaint_reason_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    if not target_user_id:
        await state.clear()
        await message.answer("Не вдалося визначити анкету для скарги.")
        return

    cur = await get_current_user_or_none(session, message.from_user.id)
    if not cur:
        await state.clear()
        await message.answer("Спочатку заповніть профіль: /start")
        return

    reason = (message.text or "").strip()
    if not reason:
        await message.answer("Будь ласка, опишіть причину текстом.")
        return

    ok, msg = await _create_complaint(session, reporter_id=cur.id, target_user_id=int(target_user_id), reason=reason)
    await message.answer(msg)
    await state.clear()
