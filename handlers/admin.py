from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from models import Like, Match, User
from services.daily_reset import reset_likes_and_skips
from services.db_reset import reset_database
from services.reset_feed import reset_feed

router = Router()


def _is_admin(cfg: Config, tg_id: int) -> bool:
    return tg_id in set(cfg.admins)


def _confirm_reset_db_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Так, скинути БД", callback_data="admin_resetdb:yes")
    builder.button(text="❌ Скасувати", callback_data="admin_resetdb:no")
    builder.adjust(1)
    return builder.as_markup()


@router.message(Command("admin"))
async def admin_help(message: Message, cfg: Config) -> None:
    if not _is_admin(cfg, message.from_user.id):
        return

    await message.answer(
        "<b>Адмін-команди</b>\n"
        "• /stats — статистика\n"
        "• /reset_swipes — скинути історію лайків/пропусків (анкети будуть показуватися заново)\n"
        "• /reset_db — ПОВНИЙ скидання бази (видаляє анкети/фото/лайки/мэтчі)\n"
        "• /reset_feed — скинути стрічку (лайки/пропуски + мэтчі, анкети/фото зберігаються)\n"
    )


@router.message(Command("stats"))
async def stats(message: Message, session: AsyncSession, cfg: Config) -> None:
    if not _is_admin(cfg, message.from_user.id):
        return

    users_cnt = int((await session.execute(select(func.count(User.id)))).scalar_one())
    active_cnt = int((await session.execute(select(func.count(User.id)).where(User.active == True))).scalar_one())  # noqa: E712
    likes_cnt = int((await session.execute(select(func.count(Like.id)))).scalar_one())
    matches_cnt = int((await session.execute(select(func.count(Match.id)))).scalar_one())

    await message.answer(
        "<b>Статистика</b>\n"
        f"Користувачів всього: {users_cnt}\n"
        f"Активних анкет: {active_cnt}\n"
        f"Лайків/пропусків (історія): {likes_cnt}\n"
        f"Мэтчів: {matches_cnt}"
    )


@router.message(Command("reset_swipes"))
async def reset_swipes(message: Message, session: AsyncSession, cfg: Config) -> None:
    if not _is_admin(cfg, message.from_user.id):
        return

    res = await reset_likes_and_skips(session)
    await message.answer(f"✅ Готово. Історію лайків/пропусків скинуто. Видалено записів: {res.deleted_likes}")


@router.message(Command("reset_feed"))
async def reset_feed_cmd(message: Message, session: AsyncSession, cfg: Config) -> None:
    """Ручне скидання стрічки: лайки/пропуски + мэтчі (анкети/фото не чіпаємо)."""
    if not _is_admin(cfg, message.from_user.id):
        return

    # Швидкий UX: відповідаємо одразу, навіть якщо SQLite трохи «думає»
    await message.answer("⏳ Скидаю стрічку (лайки/пропуски + мэтчі)…")

    res = await reset_feed(session)
    await message.answer(
        "✅ Готово. Стрічку скинуто.\n"
        f"Видалено лайків/пропусків: {res.deleted_likes}\n"
        f"Видалено мэтчів: {res.deleted_matches}"
    )


@router.message(Command("reset_db"))
async def reset_db_prompt(message: Message, cfg: Config) -> None:
    if not _is_admin(cfg, message.from_user.id):
        return

    await message.answer(
        "⚠️ <b>Увага</b>: це видалить <b>УСІ</b> дані бота (анкети, фото, лайки, мэтчі).\n"
        "Дія незворотна.\n\n"
        "Підтвердити скидання?",
        reply_markup=_confirm_reset_db_kb(),
    )


@router.callback_query(F.data.startswith("admin_resetdb:"))
async def reset_db_confirm(call: CallbackQuery, session: AsyncSession, cfg: Config) -> None:
    if not _is_admin(cfg, call.from_user.id):
        await call.answer("Недостатньо прав", show_alert=True)
        return

    decision = call.data.split(":", 1)[1]
    if decision != "yes":
        await call.answer("Скасовано")
        try:
            await call.message.edit_text("Скасовано.")
        except Exception:
            await call.message.answer("Скасовано.")
        return

    await call.answer("Скидаю…", show_alert=True)
    res = await reset_database(session)

    text = (
        "✅ <b>Базу даних скинуто</b>\n"
        f"Видалено користувачів: {res.users}\n"
        f"Видалено фото: {res.photos}\n"
        f"Видалено лайків/пропусків: {res.likes}\n"
        f"Видалено мэтчів: {res.matches}\n"
        f"Видалено логів антифлуда: {res.action_logs}"
    )

    try:
        await call.message.edit_text(text)
    except Exception:
        await call.message.answer(text)
