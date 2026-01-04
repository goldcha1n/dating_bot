from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from models import ActionLog, Complaint, Like, Match, Message as DbMessage, Photo, User
from services.daily_reset import reset_likes_and_skips
from services.db_reset import reset_database
from services.reset_feed import reset_feed

router = Router()


def _is_admin(cfg: Config, tg_id: int) -> bool:
    return tg_id in set(cfg.admins)


def _confirm_reset_db_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Так, очистити базу", callback_data="admin_resetdb:yes")
    builder.button(text="✖️ Ні", callback_data="admin_resetdb:no")
    builder.adjust(1)
    return builder.as_markup()


@router.message(Command("admin"))
async def admin_help(message: Message, cfg: Config) -> None:
    if not _is_admin(cfg, message.from_user.id):
        return

    await message.answer(
        "<b>Адмін-команди</b>\n"
        "• /stats — статистика\n"
        "• /reset_swipes — скинути лайки/скіпи (щоб оновити стрічку)\n"
        "• /reset_db — повне очищення бази (анкет, фото, лайків, матчів)\n"
        "• /reset_feed — скинути черги перегляду (лайки/матчі залишаються)\n"
        "• /clear_profiles — видалити всі профілі (users) разом з даними"
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
        f"Усього анкет: {users_cnt}\n"
        f"Активні: {active_cnt}\n"
        f"Лайки/скіпи: {likes_cnt}\n"
        f"Match: {matches_cnt}"
    )


@router.message(Command("reset_swipes"))
async def reset_swipes_cmd(message: Message, session: AsyncSession, cfg: Config) -> None:
    if not _is_admin(cfg, message.from_user.id):
        return

    res = await reset_likes_and_skips(session)
    await message.answer(
        f"Готово. Лайки/скіпи очищено. Видалено записів: {res.deleted_likes}"
    )


@router.message(Command("reset_feed"))
async def reset_feed_cmd(message: Message, session: AsyncSession, cfg: Config) -> None:
    """Скидає черги перегляду (лайки/матчі залишаються)."""
    if not _is_admin(cfg, message.from_user.id):
        return

    res = await reset_feed(session)
    await message.answer(
        "Готово. Стрічку очищено.\n"
        f"Вилучено лайків/скіпів: {res.deleted_likes}\n"
        f"Вилучено матчів: {res.deleted_matches}"
    )


@router.message(Command("reset_db"))
async def reset_db_prompt(message: Message, cfg: Config) -> None:
    if not _is_admin(cfg, message.from_user.id):
        return

    await message.answer(
        "Увага: буде видалено всі анкети, фото, лайки, матчі, логи. Продовжити?",
        reply_markup=_confirm_reset_db_kb(),
    )


@router.callback_query(F.data.startswith("admin_resetdb:"))
async def reset_db_confirm(call: CallbackQuery, session: AsyncSession, cfg: Config) -> None:
    if not _is_admin(cfg, call.from_user.id):
        await call.answer("Немає доступу", show_alert=True)
        return

    decision = call.data.split(":", 1)[1]
    if decision != "yes":
        await call.answer("Скасовано")
        try:
            await call.message.edit_text("Скасовано.")
        except Exception:
            await call.message.answer("Скасовано.")
        return

    await call.answer("Очищення...", show_alert=True)
    res = await reset_database(session)

    text = (
        "<b>Базу очищено</b>\n"
        f"Анкет: {res.users}\n"
        f"Фото: {res.photos}\n"
        f"Feedback: {res.feedback}\n"
        f"Лайки/скіпи: {res.likes}\n"
        f"Match: {res.matches}\n"
        f"Логи дій: {res.action_logs}"
    )

    try:
        await call.message.edit_text(text)
    except Exception:
        await call.message.answer(text)


@router.message(Command("clear_profiles"))
async def clear_profiles(message: Message, session: AsyncSession, cfg: Config) -> None:
    """Видаляє всі профілі (users) і привʼязані дані."""
    if not _is_admin(cfg, message.from_user.id):
        return

    users = int((await session.execute(select(func.count(User.id)))).scalar_one())
    photos = int((await session.execute(select(func.count(Photo.id)))).scalar_one())
    likes = int((await session.execute(select(func.count(Like.id)))).scalar_one())
    matches = int((await session.execute(select(func.count(Match.id)))).scalar_one())
    messages_cnt = int((await session.execute(select(func.count(DbMessage.id)))).scalar_one())
    complaints = int((await session.execute(select(func.count(Complaint.id)))).scalar_one())
    logs = int((await session.execute(select(func.count(ActionLog.id)))).scalar_one())

    await session.execute(delete(Complaint))
    await session.execute(delete(Like))
    await session.execute(delete(Match))
    await session.execute(delete(DbMessage))
    await session.execute(delete(Photo))
    await session.execute(delete(ActionLog))
    await session.execute(delete(User))
    await session.commit()

    await message.answer(
        "<b>Профілі очищено</b>\n"
        f"Користувачі: {users}\n"
        f"Фото: {photos}\n"
        f"Лайки/скіпи: {likes}\n"
        f"Match: {matches}\n"
        f"Повідомлення: {messages_cnt}\n"
        f"Скарги: {complaints}\n"
        f"Логи дій: {logs}"
    )
