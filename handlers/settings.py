from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.main_menu import BTN_SETTINGS
from keyboards.settings import open_settings_kb, settings_kb
from services.matching import get_current_user_or_none
from utils.text import format_location

router = Router()


def _scope_label(scope: str) -> str:
    return {
        "settlement": "🏠 Моє місто/село",
        "district": "🗺️ Мій район",
        "region": "📍 Моя область",
        "country": "🌍 Уся країна",
    }.get(scope, "🌍 Уся країна")


def _current_scope(user) -> str:
    scope = getattr(user, "search_scope", None)
    if scope not in {"settlement", "district", "region", "country"}:
        scope = "country" if getattr(user, "search_global", False) else "settlement"
    return scope


async def _send_settings(message_or_call, session: AsyncSession) -> None:
    cur = await get_current_user_or_none(session, message_or_call.from_user.id)
    if not cur:
        target = message_or_call.message if hasattr(message_or_call, "message") else message_or_call
        await target.answer("Спочатку створіть анкету: /start")
        return

    scope = _current_scope(cur)
    text = (
        "⚙️ <b>Налаштування</b>\n"
        f"Моя локація: {format_location(cur)}\n\n"
        "🔎 Де шукаю:\n"
        "• 🏠 Місто/село — тільки ваш населений пункт\n"
        "• 🗺️ Район — усі населені пункти вашого району\n"
        "• 📍 Область — вся область\n"
        "• 🌍 Уся країна — без обмежень\n\n"
        "🎂 Віковий фільтр — показуємо анкети приблизно вашого віку "
        "(на 3 роки молодші і до 2 років старші)\n"
        "⏸️ Пауза — ваша анкета прихована з пошуку"
    )

    kb = settings_kb(scope, cur.active, getattr(cur, "age_filter_enabled", True))

    if hasattr(message_or_call, "message"):  # CallbackQuery
        await message_or_call.message.answer(text, reply_markup=kb)
    else:  # Message
        await message_or_call.answer(text, reply_markup=kb)


@router.message(F.text.in_({BTN_SETTINGS, "Налаштування"}))
async def settings_menu(message: Message, session: AsyncSession) -> None:
    await _send_settings(message, session)


@router.callback_query(F.data == "settings:open")
async def settings_open(call: CallbackQuery, session: AsyncSession) -> None:
    await call.answer()
    await _send_settings(call, session)


@router.callback_query(F.data == "settings:toggle_scope")
async def toggle_scope(call: CallbackQuery, session: AsyncSession) -> None:
    await call.answer()
    cur = await get_current_user_or_none(session, call.from_user.id)
    if not cur:
        await call.message.answer("Спочатку створіть анкету: /start")
        return

    order = ["settlement", "district", "region", "country"]
    scope = _current_scope(cur)
    try:
        next_scope = order[(order.index(scope) + 1) % len(order)]
    except ValueError:
        next_scope = "settlement"

    cur.search_scope = next_scope
    cur.search_global = next_scope != "settlement"
    await session.commit()

    await call.message.edit_reply_markup(
        reply_markup=settings_kb(next_scope, cur.active, getattr(cur, "age_filter_enabled", True)),
    )


@router.callback_query(F.data == "settings:toggle_active")
async def toggle_active(call: CallbackQuery, session: AsyncSession) -> None:
    await call.answer()
    cur = await get_current_user_or_none(session, call.from_user.id)
    if not cur:
        await call.message.answer("Спочатку створіть анкету: /start")
        return

    cur.active = not cur.active
    await session.commit()

    await call.message.edit_reply_markup(
        reply_markup=settings_kb(_current_scope(cur), cur.active, getattr(cur, "age_filter_enabled", True)),
    )


@router.callback_query(F.data == "settings:toggle_age_filter")
async def toggle_age_filter(call: CallbackQuery, session: AsyncSession) -> None:
    await call.answer()
    cur = await get_current_user_or_none(session, call.from_user.id)
    if not cur:
        await call.message.answer("Спочатку створіть анкету: /start")
        return

    current_val = getattr(cur, "age_filter_enabled", True)
    setattr(cur, "age_filter_enabled", not current_val)
    await session.commit()

    await call.message.edit_reply_markup(
        reply_markup=settings_kb(_current_scope(cur), cur.active, getattr(cur, "age_filter_enabled", True)),
    )
