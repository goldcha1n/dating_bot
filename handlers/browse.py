from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from keyboards.inline_profiles import browse_kb
from keyboards.main_menu import BTN_BROWSE
from keyboards.settings import open_settings_kb
from models import User
from services.antiflood import is_allowed, log_action
from services.matching import (
    get_current_user_or_none,
    get_next_candidate,
    put_reaction_and_maybe_match,
)

from utils.text import render_profile_caption

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text.in_({BTN_BROWSE, "Смотреть анкеты"}))
async def browse_start(message: Message, session: AsyncSession, cfg: Config) -> None:
    cur = await get_current_user_or_none(session, message.from_user.id)
    if not cur:
        await message.answer("Сначала создайте анкету: /start")
        return

    if not cur.active:
        await message.answer("Вы поставили анкету на паузу. Включите её в настройках.", reply_markup=open_settings_kb())
        return

    await _send_next(message, session, cur, cfg)


async def _send_next(message: Message, session: AsyncSession, cur: User, cfg: Config) -> None:
    # Антифлуд по просмотрам
    if not await is_allowed(
        session=session,
        user_id=cur.id,
        actions=("view",),
        limit=cfg.view_limit_per_min,
        window_seconds=60,
    ):
        await message.answer("Слишком быстро листаете. Подождите минуту и попробуйте снова.")
        return

    candidate = await get_next_candidate(session, cur)
    if not candidate:
        await message.answer(
            "Пока нет подходящих анкет.\n\n"
            "Что можно сделать:\n"
            "• включить 🌍 поиск в любом городе\n"
            "• зайти позже",
            reply_markup=open_settings_kb(),
        )
        return

    # Логируем показ анкеты
    await log_action(session, user_id=cur.id, action="view")
    await session.commit()

    main_photo = None
    for p in candidate.photos:
        if p.is_main:
            main_photo = p.file_id
            break
    if not main_photo and candidate.photos:
        main_photo = candidate.photos[0].file_id

    kb = browse_kb(candidate.id)

    if main_photo:
        await message.answer_photo(
            photo=main_photo,
            caption=render_profile_caption(candidate),
            reply_markup=kb,
        )
    else:
        await message.answer(render_profile_caption(candidate), reply_markup=kb)


@router.callback_query(F.data.startswith("browse:"))
async def browse_react(call: CallbackQuery, session: AsyncSession, cfg: Config) -> None:
    cur = await get_current_user_or_none(session, call.from_user.id)
    if not cur:
        await call.answer("Сначала анкета", show_alert=True)
        await call.message.answer("Сначала создайте анкету: /start")
        return

    # Антифлуд по действиям
    if not await is_allowed(
        session, user_id=cur.id, actions=("action",), limit=cfg.action_limit_per_min, window_seconds=60
    ):
        await call.answer("Слишком часто", show_alert=True)
        return

    try:
        _, action, raw_id = call.data.split(":", 2)
        candidate_id = int(raw_id)
    except Exception:
        await call.answer("Ошибка кнопки", show_alert=True)
        return

    if action not in ("like", "skip"):
        await call.answer()
        return

    # Лимит на лайки
    if action == "like":
        if not await is_allowed(
            session=session,
            user_id=cur.id,
            actions=("like", "inlike_like"),
            limit=cfg.like_limit_per_hour,
            window_seconds=60 * 60,
        ):
            await call.answer("Лимит лайков", show_alert=True)
            await call.message.answer("Лимит лайков исчерпан. Попробуйте позже.")
            return

    # Быстрый “native” feedback
    await call.answer("❤️ Отправлено" if action == "like" else "➡️ Дальше")

    # Лог действий
    await log_action(session, user_id=cur.id, action="action")
    await log_action(session, user_id=cur.id, action=action)

    try:
        await put_reaction_and_maybe_match(
            session=session,
            from_user=cur,
            to_user_id=candidate_id,
            is_like=(action == "like"),
            bot=call.bot,
        )
    except Exception:
        logger.exception("Failed to process reaction")
        await call.message.answer("Произошла ошибка. Попробуйте ещё раз.")
        return

    await _send_next(call.message, session, cur, cfg)


@router.callback_query(F.data.startswith("inlike:"))
async def incoming_like_actions(call: CallbackQuery, session: AsyncSession, cfg: Config) -> None:
    """Кнопки под уведомлением 'вас лайкнули'."""
    cur = await get_current_user_or_none(session, call.from_user.id)
    if not cur:
        await call.answer("Сначала анкета", show_alert=True)
        await call.message.answer("Сначала создайте анкету: /start")
        return

    if not await is_allowed(
        session, user_id=cur.id, actions=("action",), limit=cfg.action_limit_per_min, window_seconds=60
    ):
        await call.answer("Слишком часто", show_alert=True)
        return

    try:
        _, action, raw_id = call.data.split(":", 2)
        other_id = int(raw_id)
    except Exception:
        await call.answer("Ошибка кнопки", show_alert=True)
        return

    if action not in ("like", "skip"):
        await call.answer()
        return

    if action == "like":
        if not await is_allowed(
            session=session,
            user_id=cur.id,
            actions=("like", "inlike_like"),
            limit=cfg.like_limit_per_hour,
            window_seconds=60 * 60,
        ):
            await call.answer("Лимит лайков", show_alert=True)
            await call.message.answer("Лимит лайков исчерпан. Попробуйте позже.")
            return

    await call.answer("❤️ Ответ отправлен" if action == "like" else "🙈 Ок")

    await log_action(session, user_id=cur.id, action="action")
    await log_action(session, user_id=cur.id, action=f"inlike_{action}")

    try:
        await put_reaction_and_maybe_match(
            session=session,
            from_user=cur,
            to_user_id=other_id,
            is_like=(action == "like"),
            bot=call.bot,
        )
    except Exception:
        logger.exception("Failed to process incoming-like action")
        await call.message.answer("Ошибка при обработке. Попробуйте ещё раз.")
