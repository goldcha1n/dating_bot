from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.main_menu import BTN_SETTINGS
from keyboards.settings import open_settings_kb, settings_kb
from services.matching import get_current_user_or_none

router = Router()


async def _send_settings(message_or_call, session: AsyncSession) -> None:
    cur = await get_current_user_or_none(session, message_or_call.from_user.id)
    if not cur:
        target = message_or_call.message if hasattr(message_or_call, "message") else message_or_call
        await target.answer("Сначала создайте анкету: /start")
        return

    text = (
        "⚙️ <b>Настройки</b>\n"
        "• 📍 Только в моём городе — анкеты только из вашего города\n"
        "• 🌍 В любом городе — анкеты из всех городов\n"
        "• 🎂 Возрастной фильтр — показываем анкеты примерно вашего возраста\n"
        "  (по умолчанию: на 3 года младше и до 2 лет старше)\n"
        "• ⏸️ Пауза — ваша анкета скрыта из поиска"
    )

    kb = settings_kb(cur.search_global, cur.active, getattr(cur, "age_filter_enabled", True))

    if hasattr(message_or_call, "message"):  # CallbackQuery
        await message_or_call.message.answer(text, reply_markup=kb)
    else:  # Message
        await message_or_call.answer(text, reply_markup=kb)


@router.message(F.text.in_({BTN_SETTINGS, "Настройки"}))
async def settings_menu(message: Message, session: AsyncSession) -> None:
    await _send_settings(message, session)


@router.callback_query(F.data == "settings:open")
async def settings_open(call: CallbackQuery, session: AsyncSession) -> None:
    await call.answer()
    await _send_settings(call, session)


@router.callback_query(F.data == "settings:toggle_city")
async def toggle_city(call: CallbackQuery, session: AsyncSession) -> None:
    await call.answer()
    cur = await get_current_user_or_none(session, call.from_user.id)
    if not cur:
        await call.message.answer("Сначала создайте анкету: /start")
        return

    cur.search_global = not cur.search_global
    await session.commit()

    await call.message.edit_reply_markup(
        reply_markup=settings_kb(cur.search_global, cur.active, getattr(cur, "age_filter_enabled", True)),
    )


@router.callback_query(F.data == "settings:toggle_active")
async def toggle_active(call: CallbackQuery, session: AsyncSession) -> None:
    await call.answer()
    cur = await get_current_user_or_none(session, call.from_user.id)
    if not cur:
        await call.message.answer("Сначала создайте анкету: /start")
        return

    cur.active = not cur.active
    await session.commit()

    await call.message.edit_reply_markup(
        reply_markup=settings_kb(cur.search_global, cur.active, getattr(cur, "age_filter_enabled", True)),
    )


@router.callback_query(F.data == "settings:toggle_age_filter")
async def toggle_age_filter(call: CallbackQuery, session: AsyncSession) -> None:
    await call.answer()
    cur = await get_current_user_or_none(session, call.from_user.id)
    if not cur:
        await call.message.answer("Сначала создайте анкету: /start")
        return

    # по умолчанию True; колонка добавлена миграцией, но на всякий случай через getattr/setattr
    current_val = getattr(cur, "age_filter_enabled", True)
    setattr(cur, "age_filter_enabled", not current_val)
    await session.commit()

    await call.message.edit_reply_markup(
        reply_markup=settings_kb(cur.search_global, cur.active, getattr(cur, "age_filter_enabled", True)),
    )
