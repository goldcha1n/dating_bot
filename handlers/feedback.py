from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from models import Feedback
from services.antiflood import is_allowed, log_action
from services.matching import get_current_user_or_none

logger = logging.getLogger(__name__)
router = Router()

FEEDBACK_LIMIT_PER_DAY = 3
FEEDBACK_ACTION = "feedback"


class FeedbackStates(StatesGroup):
    waiting_text = State()


def feedback_type_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🛠️ Проблема", callback_data="feedback:cat:issue")
    builder.button(text="💡 Ідея", callback_data="feedback:cat:idea")
    builder.button(text="✨ Інше", callback_data="feedback:cat:other")
    builder.adjust(2, 1)
    return builder.as_markup()


async def _is_allowed(session: AsyncSession, user_id: int) -> bool:
    return await is_allowed(
        session,
        user_id=user_id,
        actions=[FEEDBACK_ACTION],
        limit=FEEDBACK_LIMIT_PER_DAY,
        window_seconds=24 * 3600,
    )


@router.message(Command("feedback"))
async def feedback_start(message: Message, state: FSMContext, session: AsyncSession) -> None:
    user = await get_current_user_or_none(session, message.from_user.id)
    if not user:
        await state.clear()
        await message.answer("Здається, ви ще не зареєстровані. Натисніть /start, щоб створити анкету 🙂")
        return

    if not await _is_allowed(session, user.id):
        await message.answer("Можна надіслати до 3 відгуків на добу. Спробуйте пізніше ⏳")
        return

    await state.set_state(FeedbackStates.waiting_text)
    await state.update_data(category="general")
    await message.answer(
        "Поділіться, що покращити або що пішло не так. "
        "Можете додати контакти для зворотного зв'язку. Оберіть тип або просто напишіть повідомлення:",
        reply_markup=feedback_type_kb(),
    )


@router.callback_query(F.data.startswith("feedback:cat:"))
async def feedback_set_category(call: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await call.answer()
    user = await get_current_user_or_none(session, call.from_user.id)
    if not user:
        await state.clear()
        await call.message.answer("Потрібно зареєструватися. Натисніть /start 🙂")
        return

    if not await _is_allowed(session, user.id):
        await call.message.answer("Ліміт вичерпано: не більше 3 повідомлень на добу ⏳")
        await state.clear()
        return

    category = call.data.split(":")[-1]
    await state.update_data(category=category)
    await state.set_state(FeedbackStates.waiting_text)
    await call.message.answer("Прийнято! Опишіть проблему чи ідею одним повідомленням 📝")


@router.message(FeedbackStates.waiting_text)
async def feedback_save(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user = await get_current_user_or_none(session, message.from_user.id)
    if not user:
        await state.clear()
        await message.answer("Потрібно зареєструватися. Натисніть /start 🙂")
        return

    if not await _is_allowed(session, user.id):
        await message.answer("Можна надіслати до 3 відгуків на добу. Спробуйте пізніше ⏳")
        await state.clear()
        return

    text = (message.text or message.caption or "").strip()
    if not text:
        await message.answer("Будь ласка, напишіть текст відгуку 🙂")
        return
    if len(text) > 2000:
        text = text[:2000]

    data = await state.get_data()
    category = data.get("category") or "general"

    feedback = Feedback(
        user_id=user.id,
        tg_id=user.tg_id,
        username=user.username,
        category=category,
        status="new",
        description=text,
    )
    session.add(feedback)
    await log_action(session, user_id=user.id, action=FEEDBACK_ACTION)
    try:
        await session.commit()
        await message.answer("Дякуємо! Отримали ваш відгук і повернемося з відповіддю за потреби 🙌")
    except Exception:
        await session.rollback()
        logger.exception("Failed to save feedback")
        await message.answer("Не вдалося зберегти повідомлення. Спробуйте ще раз пізніше 🙁")
        return

    await state.clear()
