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
    builder.button(text="✅ Да, сбросить БД", callback_data="admin_resetdb:yes")
    builder.button(text="❌ Отмена", callback_data="admin_resetdb:no")
    builder.adjust(1)
    return builder.as_markup()


@router.message(Command("admin"))
async def admin_help(message: Message, cfg: Config) -> None:
    if not _is_admin(cfg, message.from_user.id):
        return

    await message.answer(
        "<b>Админ-команды</b>\n"
        "• /stats — статистика\n"
        "• /reset_swipes — сбросить историю лайков/скипов (анкеты будут показываться заново)\n"
        "• /reset_db — ПОЛНЫЙ сброс базы (удаляет анкеты/фото/лайки/мэтчи)\n• /reset_feed — сбросить ленту (лайки/скипы + мэтчи, анкеты/фото сохраняются)\n"
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
        f"Пользователей всего: {users_cnt}\n"
        f"Активных анкет: {active_cnt}\n"
        f"Лайков/скипов (история): {likes_cnt}\n"
        f"Мэтчей: {matches_cnt}"
    )


@router.message(Command("reset_swipes"))
async def reset_swipes(message: Message, session: AsyncSession, cfg: Config) -> None:
    if not _is_admin(cfg, message.from_user.id):
        return

    res = await reset_likes_and_skips(session)
    await message.answer(f"✅ Готово. История лайков/скипов сброшена. Удалено записей: {res.deleted_likes}")



@router.message(Command("reset_feed"))
async def reset_feed_cmd(message: Message, session: AsyncSession, cfg: Config) -> None:
    """Ручной сброс ленты: лайки/скипы + мэтчи (анкеты/фото остаются)."""
    if not _is_admin(cfg, message.from_user.id):
        return

    # Быстрый UX: отвечаем сразу, даже если SQLite чуть «думает»
    await message.answer("⏳ Сбрасываю ленту (лайки/скипы + мэтчи)…")

    res = await reset_feed(session)
    await message.answer(
        "✅ Готово. Лента сброшена.\n"
        f"Удалено лайков/скипов: {res.deleted_likes}\n"
        f"Удалено мэтчей: {res.deleted_matches}"
    )


@router.message(Command("reset_db"))
async def reset_db_prompt(message: Message, cfg: Config) -> None:
    if not _is_admin(cfg, message.from_user.id):
        return

    await message.answer(
        "⚠️ <b>Внимание</b>: это удалит <b>ВСЕ</b> данные бота (анкеты, фото, лайки, мэтчи).\n"
        "Действие необратимо.\n\n"
        "Подтвердить сброс?",
        reply_markup=_confirm_reset_db_kb(),
    )


@router.callback_query(F.data.startswith("admin_resetdb:"))
async def reset_db_confirm(call: CallbackQuery, session: AsyncSession, cfg: Config) -> None:
    if not _is_admin(cfg, call.from_user.id):
        await call.answer("Недостаточно прав", show_alert=True)
        return

    decision = call.data.split(":", 1)[1]
    if decision != "yes":
        await call.answer("Отменено")
        try:
            await call.message.edit_text("Отменено.")
        except Exception:
            await call.message.answer("Отменено.")
        return

    await call.answer("Сбрасываю…", show_alert=True)
    res = await reset_database(session)

    text = (
        "✅ <b>База данных сброшена</b>\n"
        f"Удалено пользователей: {res.users}\n"
        f"Удалено фото: {res.photos}\n"
        f"Удалено лайков/скипов: {res.likes}\n"
        f"Удалено мэтчей: {res.matches}\n"
        f"Удалено логов антифлуда: {res.action_logs}"
    )

    try:
        await call.message.edit_text(text)
    except Exception:
        await call.message.answer(text)
