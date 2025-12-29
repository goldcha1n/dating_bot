from __future__ import annotations

import logging
from typing import Optional

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import Config
from keyboards.main_menu import main_menu_kb
from keyboards.inline_profiles import gender_kb, looking_for_kb, skip_about_kb, to_menu_inline_kb
from models import Photo, User
from utils.text import gender_to_code, looking_for_to_code, render_profile_caption

logger = logging.getLogger(__name__)
router = Router()


class Registration(StatesGroup):
    name = State()
    age = State()
    gender = State()
    looking_for = State()
    city = State()
    about = State()
    photos = State()


async def _get_user_by_tg(session: AsyncSession, tg_id: int) -> Optional[User]:
    res = await session.execute(select(User).where(User.tg_id == tg_id))
    return res.scalar_one_or_none()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession, cfg: Config) -> None:
    user = await _get_user_by_tg(session, message.from_user.id)
    if user:
        await state.clear()
        await message.answer("У вас уже есть анкета.", reply_markup=main_menu_kb())
        return

    await state.clear()
    await message.answer(
        "Привет! Давай быстро сделаем анкету.\n\n"
        "<b>Шаг 1/7</b> — как тебя зовут?",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(Registration.name)


@router.message(Registration.name)
async def reg_name(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("Имя слишком короткое. Напишите имя (минимум 2 символа).")
        return

    await state.update_data(name=text)
    await message.answer("<b>Шаг 2/7</b> — сколько тебе лет? (16–99)")
    await state.set_state(Registration.age)


@router.message(Registration.age)
async def reg_age(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    try:
        age = int(raw)
    except ValueError:
        await message.answer("Введите возраст числом (16–99).")
        return

    if age < 16 or age > 99:
        await message.answer("Возраст должен быть от 16 до 99.")
        return

    await state.update_data(age=age)
    await message.answer("<b>Шаг 3/7</b> — выберите пол:", reply_markup=gender_kb())
    await state.set_state(Registration.gender)


@router.message(Registration.gender)
async def reg_gender(message: Message, state: FSMContext) -> None:
    code = gender_to_code((message.text or "").strip())
    if not code:
        await message.answer("Выберите пол кнопкой ниже:", reply_markup=gender_kb())
        return

    await state.update_data(gender=code)
    await message.answer("<b>Шаг 4/7</b> — кого ищете?", reply_markup=looking_for_kb())
    await state.set_state(Registration.looking_for)


@router.message(Registration.looking_for)
async def reg_looking_for(message: Message, state: FSMContext) -> None:
    code = looking_for_to_code((message.text or "").strip())
    if not code:
        await message.answer("Выберите вариант кнопкой ниже:", reply_markup=looking_for_kb())
        return

    await state.update_data(looking_for=code)
    await message.answer("<b>Шаг 5/7</b> — ваш город?")
    await state.set_state(Registration.city)


@router.message(Registration.city)
async def reg_city(message: Message, state: FSMContext) -> None:
    city = (message.text or "").strip()
    if not city:
        await message.answer("Город не должен быть пустым. Введите город.")
        return

    await state.update_data(city=city)
    await message.answer(
        "<b>Шаг 6/7</b> — пару слов о себе (можно пропустить).",
        reply_markup=skip_about_kb(),
    )
    await state.set_state(Registration.about)


@router.message(Registration.about)
async def reg_about(message: Message, state: FSMContext, cfg: Config) -> None:
    text = (message.text or "").strip()

    if text.lower() in ("пропустить", "⏭️ пропустить"):
        await state.update_data(about=None)
    else:
        if len(text) < cfg.about_min_len:
            await message.answer(
                f"Коротко. Минимум {cfg.about_min_len} символов, или нажмите «Пропустить».",
                reply_markup=skip_about_kb(),
            )
            return
        await state.update_data(about=text)

    await message.answer(
        "<b>Шаг 7/7</b> — отправьте фото (минимум 1).",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(Registration.photos)
    await state.update_data(photo_file_ids=[])


@router.message(Registration.photos, F.photo)
async def reg_photo(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    file_ids = list(data.get("photo_file_ids", []))

    file_id = message.photo[-1].file_id
    file_ids.append(file_id)

    await state.update_data(photo_file_ids=file_ids)

    # MVP: завершаем после первого фото
    await _finish_registration(message, state, session)


@router.message(Registration.photos)
async def reg_photo_invalid(message: Message) -> None:
    await message.answer("Нужно фото (сообщением с фотографией). Пришлите фото.")


async def _finish_registration(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    tg = message.from_user

    user = User(
        tg_id=tg.id,
        username=tg.username,
        name=data["name"],
        age=int(data["age"]),
        gender=data["gender"],
        looking_for=data["looking_for"],
        city=data["city"],
        about=data.get("about"),
        search_global=False,
        active=True,
    )
    session.add(user)
    await session.flush()

    photos = data.get("photo_file_ids", [])
    for i, fid in enumerate(photos[:3]):
        session.add(Photo(user_id=user.id, file_id=fid, is_main=(i == 0)))

    await session.commit()
    await state.clear()

    await message.answer_photo(
        photo=photos[0],
        caption=render_profile_caption(user),
        reply_markup=to_menu_inline_kb(),
    )
    await message.answer("Готово. Добро пожаловать!", reply_markup=main_menu_kb())
