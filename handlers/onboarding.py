from __future__ import annotations

import logging
from typing import Optional

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from keyboards.main_menu import main_menu_kb
from keyboards.inline_profiles import gender_kb, looking_for_kb, skip_about_kb, to_menu_inline_kb
from keyboards.locations import (
    districts_kb,
    hromadas_kb,
    regions_kb,
    search_scope_kb,
    settlement_type_kb,
    settlements_kb,
)
from models import Photo, User
from services.location_repo import LocationRepository
from utils.locations import default_location, normalize_choice, normalize_text
from utils.text import gender_to_code, looking_for_to_code, render_profile_caption

logger = logging.getLogger(__name__)
router = Router()


def _is_back(message: Message) -> bool:
    return (message.text or "").strip().lower() in {"назад", "back"}


class Registration(StatesGroup):
    name = State()
    age = State()
    gender = State()
    looking_for = State()
    region = State()
    district = State()
    hromada = State()
    settlement = State()
    settlement_type = State()
    search_scope = State()
    about = State()
    photos = State()


async def _get_user_by_tg(session: AsyncSession, tg_id: int) -> Optional[User]:
    res = await session.execute(select(User).where(User.tg_id == tg_id))
    return res.scalar_one_or_none()


def _clip(text: str, max_len: int = 128) -> str:
    return normalize_text(text)[:max_len]


async def _prompt_region(message: Message, state: FSMContext, session: AsyncSession) -> None:
    repo = LocationRepository(session)
    regions = await repo.list_regions()
    await state.update_data(region_options=regions)
    await message.answer(
        "<b>Крок 5/12</b> — обери область кнопкою або введи вручну:",
        reply_markup=regions_kb([r.name for r in regions]),
    )
    await state.set_state(Registration.region)


async def _prompt_district(message: Message, state: FSMContext, session: AsyncSession, region_code: str) -> None:
    repo = LocationRepository(session)
    districts = await repo.list_districts(region_code)
    capital_by_region = {
        "UA05000000000010236": "Вінниця",
        "UA07000000000024379": "Луцьк",
        "UA12000000000090473": "Дніпро",
        "UA14000000000091971": "Донецьк",
        "UA18000000000041385": "Житомир",
        "UA21000000000011690": "Ужгород",
        "UA23000000000064947": "Запоріжжя",
        "UA26000000000069363": "Івано-Франківськ",
        "UA32000000000030281": "Київ",
        "UA35000000000016081": "Кропивницький",
        "UA44000000000018893": "Луганськ",
        "UA46000000000026241": "Львів",
        "UA48000000000039575": "Миколаїв",
        "UA51000000000030770": "Одеса",
        "UA53000000000028050": "Полтава",
        "UA56000000000066151": "Рівне",
        "UA59000000000057109": "Суми",
        "UA61000000000060328": "Тернопіль",
        "UA63000000000041885": "Харків",
        "UA65000000000030969": "Херсон",
        "UA68000000000099709": "Хмельницький",
        "UA71000000000010357": "Черкаси",
        "UA73000000000044923": "Чернівці",
        "UA74000000000025378": "Чернігів",
        "UA01000000000013043": "Сімферополь",
        "UA85000000000065278": "Севастополь",
        "UA80000000000093317": "Київ",
    }
    capital = capital_by_region.get(region_code)
    await state.update_data(district_options=districts, region_capital=capital)

    builder = InlineKeyboardBuilder()
    if capital:
        builder.button(text=f"м. {capital}", callback_data="loc:d:capital")
    for idx, d in enumerate(districts):
        builder.button(text=d.name, callback_data=f"loc:d:{idx}")
    builder.button(text="Без району", callback_data="loc:d:none")
    builder.button(text="Назад", callback_data="loc:d:back")
    builder.adjust(2)

    await message.answer(
        "<b>Крок 6/12</b> — обери район (кнопкою) або «Без району»/«Інше»:",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(Registration.district)


async def _prompt_hromada(
    message: Message, state: FSMContext, session: AsyncSession, region_code: str, district_code: Optional[str]
) -> None:
    repo = LocationRepository(session)
    hromadas = await repo.list_hromadas(region_code, district_code or "")
    await state.update_data(hromada_options=hromadas)

    if hromadas:
        await message.answer(
            "<b>Крок 7/12</b> — обери громаду (кнопкою) або натисни «Назад»:",
            reply_markup=hromadas_kb([h.name for h in hromadas]),
        )
        await state.set_state(Registration.hromada)
    else:
        await message.answer(
            "Немає громад для вибраного району. Натисніть «Назад», щоб повернутись.",
            reply_markup=hromadas_kb([]),
        )
        await state.set_state(Registration.hromada)


async def _prompt_settlement(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    region_code: str,
    district_code: Optional[str],
    hromada_code: Optional[str],
    categories: set[str] | None = None,
) -> None:
    repo = LocationRepository(session)
    settlements = await repo.list_settlements(region_code, district_code or None, hromada_code or None, categories=categories)
    if not settlements and district_code:
        settlements = await repo.list_settlements_by_district(region_code, district_code, categories=categories)
    await state.update_data(settlement_options=settlements)

    if settlements:
        await message.answer(
            "<b>Крок 8/12</b> — обери населений пункт (кнопкою) або натисни «Назад»:",
            reply_markup=settlements_kb([s.name for s in settlements]),
        )
        await state.set_state(Registration.settlement)
    else:
        await message.answer(
            "Немає населених пунктів у вибраному фільтрі. Натисніть «Назад», щоб повернутись.",
            reply_markup=settlements_kb([]),
        )
        await state.set_state(Registration.settlement)


async def _prompt_settlement_type(message: Message, state: FSMContext) -> None:
    await message.answer("<b>Крок 9/12</b> — це місто чи село?", reply_markup=settlement_type_kb())
    await state.set_state(Registration.settlement_type)


async def _prompt_search_scope(message: Message, state: FSMContext, current: str | None = None) -> None:
    await message.answer(
        "<b>Крок 10/12</b> — де шукаємо людей?",
        reply_markup=search_scope_kb(current),
    )
    await state.set_state(Registration.search_scope)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession, cfg: Config) -> None:
    user = await _get_user_by_tg(session, message.from_user.id)
    if user:
        await state.clear()
        await message.answer("У вас вже є анкета.", reply_markup=main_menu_kb())
        return

    await state.clear()
    await message.answer(
        "Привіт! Давай швидко заповнимо анкету.\n\n"
        "<b>Крок 1/12</b> — як тебе звати?",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(Registration.name)


@router.message(Registration.name)
async def reg_name(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("Закоротко. Напишіть ім'я (мінімум 2 символи).")
        return

    await state.update_data(name=text)
    await message.answer("<b>Крок 2/12</b> — скільки тобі років? (16–99)")
    await state.set_state(Registration.age)


@router.message(Registration.age)
async def reg_age(message: Message, state: FSMContext) -> None:
    if _is_back(message):
        await message.answer("Повернувся. Як тебе звати?")
        await state.set_state(Registration.name)
        return
    raw = (message.text or "").strip()
    try:
        age = int(raw)
    except ValueError:
        await message.answer("Введіть вік числом (16–99).")
        return

    if age < 16 or age > 99:
        await message.answer("Вік має бути від 16 до 99.")
        return

    await state.update_data(age=age)
    await message.answer("<b>Крок 3/12</b> — оберіть стать:", reply_markup=gender_kb())
    await state.set_state(Registration.gender)


@router.message(Registration.gender)
async def reg_gender(message: Message, state: FSMContext) -> None:
    if _is_back(message):
        await message.answer("<b>Крок 2/12</b> — скільки тобі років? (16–99)")
        await state.set_state(Registration.age)
        return
    code = gender_to_code((message.text or "").strip())
    if not code:
        await message.answer("Оберіть стать кнопкою нижче:", reply_markup=gender_kb())
        return

    await state.update_data(gender=code)
    await message.answer("<b>Крок 4/12</b> — кого шукаєте?", reply_markup=looking_for_kb())
    await state.set_state(Registration.looking_for)


@router.message(Registration.looking_for)
async def reg_looking_for(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if _is_back(message):
        await message.answer("<b>Крок 3/12</b> — оберіть стать:", reply_markup=gender_kb())
        await state.set_state(Registration.gender)
        return
    code = looking_for_to_code((message.text or "").strip())
    if not code:
        await message.answer("Оберіть варіант кнопкою нижче:", reply_markup=looking_for_kb())
        return

    await state.update_data(looking_for=code)
    await _prompt_region(message, state, session)


@router.callback_query(Registration.region, F.data.startswith("loc:r:"))
async def region_pick(call, state: FSMContext, session: AsyncSession) -> None:
    await call.answer()
    parts = call.data.split(":")
    action = parts[2]
    data = await state.get_data()
    regions = data.get("region_options", [])

    if action == "back":
        await call.message.answer("<b>Крок 4/12</b> — кого шукаєте?", reply_markup=looking_for_kb())
        await state.set_state(Registration.looking_for)
        return

    try:
        idx = int(action)
        region_item = regions[idx]
    except Exception:
        await call.message.answer("Помилка вибору області. Введіть вручну.")
        await state.set_state(Registration.region_manual)
        return

    await state.update_data(region=region_item.name, region_code=region_item.code)
    await _prompt_district(call.message, state, session, region_item.code)


@router.callback_query(Registration.district, F.data.startswith("loc:d:"))
async def district_pick(call, state: FSMContext, session: AsyncSession) -> None:
    await call.answer()
    parts = call.data.split(":")
    action = parts[2]
    idx_part = parts[3] if len(parts) > 3 else None
    data = await state.get_data()
    districts = data.get("district_options", [])
    region_code = data.get("region_code")
    capital = data.get("region_capital")

    if action == "capital" and capital:
        await state.update_data(
            district=None,
            district_code=None,
            hromada=None,
            hromada_code=None,
            settlement=capital,
            settlement_code=None,
            settlement_type="city",
        )
        await _prompt_search_scope(call.message, state)
        return
    if action == "back":
        await _prompt_region(call.message, state, session)
        return
    if action == "none":
        await state.update_data(district=None, district_code=None)
        await _prompt_settlement(call.message, state, session, region_code, None, None)
        return

    try:
        idx = int(idx_part or action)
        district_item = districts[idx]
    except Exception:
        await call.message.answer("Помилка вибору району. Спробуйте ще раз або натисніть «Назад».")
        return

    await state.update_data(district=district_item.name, district_code=district_item.code)
    await _prompt_hromada(call.message, state, session, region_code, district_item.code)


@router.callback_query(Registration.hromada, F.data.startswith("loc:h:"))
async def hromada_pick(call, state: FSMContext, session: AsyncSession) -> None:
    await call.answer()
    _, _, raw = call.data.split(":", 2)
    data = await state.get_data()
    hromadas = data.get("hromada_options", [])

    if raw == "back":
        await _prompt_district(call.message, state, session, data.get("region_code"))
        return

    try:
        idx = int(raw)
        hromada_item = hromadas[idx]
    except Exception:
        await call.message.answer("Помилка вибору громади. Введіть вручну.")
        await state.set_state(Registration.hromada_manual)
        return

    await state.update_data(hromada=hromada_item.name, hromada_code=hromada_item.code)
    await _prompt_settlement(
        call.message,
        state,
        session,
        data.get("region_code"),
        data.get("district_code"),
        hromada_item.code,
    )


@router.callback_query(Registration.settlement, F.data.startswith("loc:s:"))
async def settlement_pick(call, state: FSMContext, session: AsyncSession) -> None:
    await call.answer()
    _, _, raw = call.data.split(":", 2)
    data = await state.get_data()
    settlements = data.get("settlement_options", [])

    if raw == "back":
        await _prompt_hromada(
            call.message, state, session, data.get("region_code"), data.get("district_code")
        )
        return

    try:
        idx = int(raw)
        settlement_item = settlements[idx]
    except Exception:
        await call.message.answer("Помилка вибору. Введіть населений пункт вручну.")
        await state.set_state(Registration.settlement_manual)
        return

    await state.update_data(settlement=settlement_item.name, settlement_code=settlement_item.code)
    await _prompt_settlement_type(call.message, state)


@router.callback_query(Registration.settlement_type, F.data.startswith("loc:type:"))
async def settlement_type_pick(call, state: FSMContext) -> None:
    await call.answer()
    _, _, value = call.data.split(":", 2)
    if value not in {"city", "village"}:
        await call.message.answer("Оберіть із кнопок: місто чи село.")
        return
    await state.update_data(settlement_type=value)
    await _prompt_search_scope(call.message, state)


@router.message(Registration.settlement_type)
async def settlement_type_back(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if _is_back(message):
        data = await state.get_data()
        await _prompt_settlement(
            message,
            state,
            session,
            data.get("region_code"),
            data.get("district_code"),
            data.get("hromada_code"),
        )
        return
    await message.answer("Оберіть із кнопок: місто чи село.", reply_markup=settlement_type_kb())


@router.callback_query(Registration.search_scope, F.data.startswith("loc:scope:"))
async def search_scope_pick(call, state: FSMContext) -> None:
    await call.answer()
    _, _, scope = call.data.split(":", 2)
    if scope not in {"settlement", "district", "region", "country"}:
        await call.message.answer("Оберіть варіант із кнопок.")
        return
    await state.update_data(search_scope=scope)
    await call.message.answer(
        "<b>Крок 11/12</b> — кілька слів про себе (можна пропустити).",
        reply_markup=skip_about_kb(),
    )
    await state.set_state(Registration.about)


@router.message(Registration.search_scope)
async def search_scope_back(message: Message, state: FSMContext) -> None:
    if _is_back(message):
        await _prompt_settlement_type(message, state)
        return
    await message.answer("Оберіть варіант із кнопок нижче.", reply_markup=search_scope_kb())


@router.message(Registration.about)
async def reg_about(message: Message, state: FSMContext, cfg: Config) -> None:
    if _is_back(message):
        data = await state.get_data()
        await _prompt_search_scope(message, state, data.get("search_scope"))
        return
    text = (message.text or "").strip()

    skip_values = {"пропустить", "⏭️ пропустить", "пропустити", "⏭️ пропустити", "-"}
    if text.lower() in skip_values:
        await state.update_data(about=None)
    else:
        if len(text) < cfg.about_min_len:
            await message.answer(
                f"Закоротко. Мінімум {cfg.about_min_len} символів або натисніть «Пропустити».",
                reply_markup=skip_about_kb(),
            )
            return
        await state.update_data(about=text)

    await message.answer(
        "<b>Крок 12/12</b> — надішліть фото (мінімум 1).",
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

    # MVP: завершуємо після першого фото
    await _finish_registration(message, state, session)


@router.message(Registration.photos)
async def reg_photo_invalid(message: Message, state: FSMContext) -> None:
    if _is_back(message):
        await message.answer(
            "<b>Крок 11/12</b> — кілька слів про себе (можна пропустити).",
            reply_markup=skip_about_kb(),
        )
        await state.set_state(Registration.about)
        return
    await message.answer("Потрібне фото (повідомлення з фотографією). Надішліть фото.")


async def _finish_registration(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    tg = message.from_user

    loc_defaults = default_location()
    region = _clip(data.get("region") or loc_defaults["region"])
    district = _clip(data.get("district") or "") or None
    hromada = _clip(data.get("hromada") or "") or None
    settlement = _clip(data.get("settlement") or loc_defaults["settlement"])
    settlement_type = data.get("settlement_type") or loc_defaults["settlement_type"]
    search_scope = data.get("search_scope") or loc_defaults["search_scope"]
    search_global = search_scope != "settlement"

    user = User(
        tg_id=tg.id,
        username=tg.username,
        first_name=tg.first_name,
        last_name=tg.last_name,
        name=data["name"],
        age=int(data["age"]),
        gender=data["gender"],
        looking_for=data["looking_for"],
        city=settlement,
        region=region,
        district=district,
        hromada=hromada,
        settlement=settlement,
        settlement_type=settlement_type,
        search_scope=search_scope,
        about=data.get("about"),
        search_global=search_global,
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
    await message.answer("Готово. Ласкаво просимо!", reply_markup=main_menu_kb())
