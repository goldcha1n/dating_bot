from __future__ import annotations

import logging
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Config
from keyboards.inline_profiles import confirm_delete_kb, gender_kb, looking_for_kb, profile_manage_kb
from keyboards.main_menu import BTN_PROFILE, main_menu_kb
from models import Photo, User
from services.matching import delete_user_account, get_current_user_or_none
from utils.text import gender_to_code, looking_for_to_code, render_profile_caption

logger = logging.getLogger(__name__)
router = Router()


class EditProfile(StatesGroup):
    name = State()
    age = State()
    gender = State()
    looking_for = State()
    city = State()
    about = State()
    photo = State()


async def _load_user(session: AsyncSession, tg_id: int) -> User | None:
    res = await session.execute(
        select(User).options(selectinload(User.photos)).where(User.tg_id == tg_id)
    )
    return res.scalar_one_or_none()


async def _send_profile(message: Message, user: User) -> None:
    photo_id = None
    for p in user.photos:
        if p.is_main:
            photo_id = p.file_id
            break
    if not photo_id and user.photos:
        photo_id = user.photos[0].file_id

    if photo_id:
        await message.answer_photo(photo=photo_id, caption=render_profile_caption(user), reply_markup=profile_manage_kb())
    else:
        await message.answer(render_profile_caption(user), reply_markup=profile_manage_kb())


@router.message(F.text.in_({BTN_PROFILE, "Моя анкета"}))
async def my_profile(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    user = await _load_user(session, message.from_user.id)
    if not user:
        await message.answer("Спочатку створіть анкету: /start")
        return
    await _send_profile(message, user)


@router.callback_query(F.data == "profile:edit_name")
async def edit_name(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(EditProfile.name)
    await call.message.answer("Введіть нове ім'я (мінімум 2 символи):", reply_markup=ReplyKeyboardRemove())


@router.message(EditProfile.name)
async def edit_name_save(message: Message, session: AsyncSession, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("Закоротко. Введіть ім'я (мінімум 2 символи).")
        return

    user = await get_current_user_or_none(session, message.from_user.id)
    if not user:
        await message.answer("Спочатку створіть анкету: /start")
        return

    user.name = text
    await session.commit()
    await state.clear()
    await message.answer("✅ Ім'я оновлено.", reply_markup=main_menu_kb())


@router.callback_query(F.data == "profile:edit_age")
async def edit_age(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(EditProfile.age)
    await call.message.answer("Введіть вік (16–99):", reply_markup=ReplyKeyboardRemove())


@router.message(EditProfile.age)
async def edit_age_save(message: Message, session: AsyncSession, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    try:
        age = int(raw)
    except ValueError:
        await message.answer("Введіть вік числом (16–99).")
        return
    if age < 16 or age > 99:
        await message.answer("Вік має бути від 16 до 99.")
        return

    user = await get_current_user_or_none(session, message.from_user.id)
    if not user:
        await message.answer("Спочатку створіть анкету: /start")
        return

    user.age = age
    await session.commit()
    await state.clear()
    await message.answer("✅ Вік оновлено.", reply_markup=main_menu_kb())


@router.callback_query(F.data == "profile:edit_gender")
async def edit_gender(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(EditProfile.gender)
    await call.message.answer("Оберіть стать:", reply_markup=gender_kb())


@router.message(EditProfile.gender)
async def edit_gender_save(message: Message, session: AsyncSession, state: FSMContext) -> None:
    code = gender_to_code((message.text or "").strip())
    if not code:
        await message.answer("Оберіть стать кнопкою нижче:", reply_markup=gender_kb())
        return

    user = await get_current_user_or_none(session, message.from_user.id)
    if not user:
        await message.answer("Спочатку створіть анкету: /start")
        return

    user.gender = code
    await session.commit()
    await state.clear()
    await message.answer("✅ Стать оновлено.", reply_markup=main_menu_kb())


@router.callback_query(F.data == "profile:edit_looking_for")
async def edit_looking_for(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(EditProfile.looking_for)
    await call.message.answer("Кого шукаєте?", reply_markup=looking_for_kb())


@router.message(EditProfile.looking_for)
async def edit_looking_for_save(message: Message, session: AsyncSession, state: FSMContext) -> None:
    code = looking_for_to_code((message.text or "").strip())
    if not code:
        await message.answer("Оберіть варіант кнопкою нижче:", reply_markup=looking_for_kb())
        return

    user = await get_current_user_or_none(session, message.from_user.id)
    if not user:
        await message.answer("Спочатку створіть анкету: /start")
        return

    user.looking_for = code
    await session.commit()
    await state.clear()
    await message.answer("✅ Налаштування оновлено.", reply_markup=main_menu_kb())


@router.callback_query(F.data == "profile:edit_city")
async def edit_city(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(EditProfile.city)
    await call.message.answer(
        "Введіть локацію у форматі:\n"
        "Область, Район (опційно), Населений пункт\n\n"
        "Наприклад:\n"
        "Львівська, Дрогобицький, Трускавець\n"
        "або просто: Київ\n\n"
        "Якщо це село — додайте слово «село» в кінці.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(EditProfile.city)
async def edit_city_save(message: Message, session: AsyncSession, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    parts = [p.strip() for p in re.split(r"[;,]", raw) if p.strip()]
    if not parts:
        await message.answer("Локація не може бути порожньою. Введіть ще раз.")
        return

    if len(parts) == 1:
        region, district, settlement = parts[0], None, parts[0]
    elif len(parts) == 2:
        region, district, settlement = parts[0], None, parts[1]
    else:
        region, district, settlement = parts[0], parts[1] or None, parts[2]

    user = await get_current_user_or_none(session, message.from_user.id)
    if not user:
        await message.answer("Спочатку створіть анкету: /start")
        return

    is_village = raw.lower().endswith("село") or " село" in raw.lower()
    user.city = settlement
    user.region = region
    user.district = district
    user.hromada = None
    user.settlement = settlement
    user.settlement_type = "village" if is_village else getattr(user, "settlement_type", "city")
    await session.commit()
    await state.clear()
    await message.answer("✅ Локацію оновлено.", reply_markup=main_menu_kb())


@router.callback_query(F.data == "profile:edit_about")
async def edit_about(call: CallbackQuery, state: FSMContext, cfg: Config) -> None:
    await call.answer()
    await state.set_state(EditProfile.about)
    await call.message.answer(
        f"Введіть новий текст «Про себе» (мінімум {cfg.about_min_len} символів) або напишіть «-», щоб очистити:",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(EditProfile.about)
async def edit_about_save(message: Message, session: AsyncSession, state: FSMContext, cfg: Config) -> None:
    text = (message.text or "").strip()
    if text == "-":
        text = ""

    if text and len(text) < cfg.about_min_len:
        await message.answer(f"Закоротко. Мінімум {cfg.about_min_len} символів або «-» щоб очистити.")
        return

    user = await get_current_user_or_none(session, message.from_user.id)
    if not user:
        await message.answer("Спочатку створіть анкету: /start")
        return

    user.about = text or None
    await session.commit()
    await state.clear()
    await message.answer("✅ Текст оновлено.", reply_markup=main_menu_kb())


@router.callback_query(F.data == "profile:edit_photo")
async def edit_photo(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(EditProfile.photo)
    await call.message.answer("Надішліть нове фото (воно стане головним):", reply_markup=ReplyKeyboardRemove())


@router.message(EditProfile.photo, F.photo)
async def edit_photo_save(message: Message, session: AsyncSession, state: FSMContext) -> None:
    user = await _load_user(session, message.from_user.id)
    if not user:
        await message.answer("Спочатку створіть анкету: /start")
        return

    new_file_id = message.photo[-1].file_id

    for p in user.photos:
        p.is_main = False

    session.add(Photo(user_id=user.id, file_id=new_file_id, is_main=True))
    await session.commit()
    await state.clear()

    await message.answer("✅ Фото оновлено.", reply_markup=main_menu_kb())


@router.message(EditProfile.photo)
async def edit_photo_invalid(message: Message) -> None:
    await message.answer("Потрібно надіслати фото.")


@router.callback_query(F.data == "profile:delete")
async def delete_prompt(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.answer(
        "⚠️ Точно видалити анкету? Це дія незворотна.",
        reply_markup=confirm_delete_kb(),
    )


@router.callback_query(F.data == "profile_delete:yes")
async def delete_yes(call: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await call.answer()
    await delete_user_account(session, call.from_user.id)
    await state.clear()
    await call.message.answer("Анкету видалено. Щоб створити нову — /start", reply_markup=main_menu_kb())


@router.callback_query(F.data == "profile_delete:no")
async def delete_no(call: CallbackQuery) -> None:
    await call.answer("Ок")
    await call.message.answer("Скасовано.", reply_markup=main_menu_kb())
