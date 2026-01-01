from __future__ import annotations

import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Config
from keyboards.inline_profiles import confirm_delete_kb, gender_kb, looking_for_kb, profile_manage_kb
from keyboards.main_menu import BTN_PROFILE, main_menu_kb
from keyboards.locations import districts_kb, hromadas_kb, regions_kb, settlement_type_kb, settlements_kb
from models import Photo, User
from services.location_repo import LocationRepository
from services.matching import delete_user_account, get_current_user_or_none
from utils.text import gender_to_code, looking_for_to_code, render_profile_caption

logger = logging.getLogger(__name__)
router = Router()


def _is_back(text: str | None) -> bool:
    return (text or "").strip().lower() in {"назад", "back"}


class EditProfile(StatesGroup):
    name = State()
    age = State()
    gender = State()
    looking_for = State()
    city = State()
    region = State()
    district = State()
    hromada = State()
    settlement = State()
    settlement_type = State()
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
async def edit_city(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await call.answer()
    user = await get_current_user_or_none(session, call.from_user.id)
    if not user:
        await state.clear()
        await call.message.answer("Анкету не знайдено, спробуйте /start.")
        return
    await state.clear()
    await _prompt_region_edit(call.message, state, session)


async def _prompt_region_edit(message: Message, state: FSMContext, session: AsyncSession) -> None:
    repo = LocationRepository(session)
    regions = await repo.list_regions()
    await state.update_data(region_options=regions)
    await message.answer("Оберіть область кнопкою:", reply_markup=regions_kb([r.name for r in regions]))
    await state.set_state(EditProfile.region)


async def _prompt_district_edit(
    message: Message, state: FSMContext, session: AsyncSession, region_code: str
) -> None:
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
    await state.update_data(district_options=districts, region_capital=capital, region_code=region_code)

    builder = InlineKeyboardBuilder()
    if capital:
        builder.button(text=f"м. {capital}", callback_data="loc:d:capital")
    for idx, d in enumerate(districts):
        builder.button(text=d.name, callback_data=f"loc:d:{idx}")
    builder.button(text="Без району", callback_data="loc:d:none")
    builder.button(text="Назад", callback_data="loc:d:back")
    builder.adjust(2)

    await message.answer("Оберіть район (кнопкою) або «Без району»:", reply_markup=builder.as_markup())
    await state.set_state(EditProfile.district)


async def _prompt_hromada_edit(
    message: Message, state: FSMContext, session: AsyncSession, region_code: str, district_code: str | None
) -> None:
    repo = LocationRepository(session)
    hromadas = await repo.list_hromadas(region_code, district_code or "")
    await state.update_data(hromada_options=hromadas)

    builder = InlineKeyboardBuilder()
    for idx, h in enumerate(hromadas):
        builder.button(text=h.name, callback_data=f"loc:h:{idx}")
    builder.button(text="Назад", callback_data="loc:h:back")
    builder.adjust(2)

    if hromadas:
        await message.answer("Оберіть громаду (кнопкою):", reply_markup=builder.as_markup())
    else:
        await message.answer("Громад не знайдено. Натисніть «Назад».", reply_markup=builder.as_markup())
    await state.set_state(EditProfile.hromada)


async def _prompt_settlement_edit(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    region_code: str,
    district_code: str | None,
    hromada_code: str | None,
    categories: set[str] | None = None,
) -> None:
    repo = LocationRepository(session)
    settlements = await repo.list_settlements(region_code, district_code or None, hromada_code or None, categories=categories)
    if not settlements and district_code:
        settlements = await repo.list_settlements_by_district(region_code, district_code, categories=categories)
    await state.update_data(settlement_options=settlements)

    builder = InlineKeyboardBuilder()
    for idx, s in enumerate(settlements):
        builder.button(text=s.name, callback_data=f"loc:s:{idx}")
    builder.button(text="Назад", callback_data="loc:s:back")
    builder.adjust(2)

    if settlements:
        await message.answer("Оберіть населений пункт (кнопкою):", reply_markup=builder.as_markup())
    else:
        await message.answer("Населених пунктів не знайдено. Натисніть «Назад».", reply_markup=builder.as_markup())
    await state.set_state(EditProfile.settlement)


async def _save_location_and_finish(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    tg_id = getattr(getattr(message, "chat", None), "id", None) or getattr(message.from_user, "id", None)
    user = await get_current_user_or_none(session, tg_id)
    if not user:
        await message.answer("Анкету не знайдено, спробуйте /start.")
        await state.clear()
        return

    user.region = data.get("region")
    user.district = data.get("district")
    user.hromada = data.get("hromada")
    settlement = data.get("settlement")
    user.settlement = settlement
    user.city = settlement
    user.settlement_type = data.get("settlement_type") or "city"

    await session.commit()
    await state.clear()
    await message.answer("✅ Локацію оновлено.", reply_markup=main_menu_kb())


@router.callback_query(EditProfile.region, F.data.startswith("loc:r:"))
async def region_pick(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await call.answer()
    action = call.data.split(":")[2]
    data = await state.get_data()
    regions = data.get("region_options", [])

    if action == "back":
        await state.clear()
        await call.message.answer("Скасовано.", reply_markup=profile_manage_kb())
        return

    try:
        idx = int(action)
        region_item = regions[idx]
    except Exception:
        await call.message.answer("Не вдалося розпізнати область. Спробуйте ще раз.")
        return

    await state.update_data(region=region_item.name, region_code=region_item.code)
    await _prompt_district_edit(call.message, state, session, region_item.code)


@router.callback_query(EditProfile.district, F.data.startswith("loc:d:"))
async def district_pick(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
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
        await _save_location_and_finish(call.message, state, session)
        return

    if action == "back":
        await _prompt_region_edit(call.message, state, session)
        return

    if action == "none":
        await state.update_data(district=None, district_code=None)
        await _prompt_settlement_edit(call.message, state, session, region_code, None, None)
        return

    try:
        idx = int(idx_part or action)
        district_item = districts[idx]
    except Exception:
        await call.message.answer("Не вдалося розпізнати район. Спробуйте ще раз.")
        return

    await state.update_data(district=district_item.name, district_code=district_item.code)
    await _prompt_hromada_edit(call.message, state, session, region_code, district_item.code)


@router.callback_query(EditProfile.hromada, F.data.startswith("loc:h:"))
async def hromada_pick(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await call.answer()
    _, _, raw = call.data.split(":", 2)
    data = await state.get_data()
    hromadas = data.get("hromada_options", [])
    region_code = data.get("region_code")
    district_code = data.get("district_code")

    if raw == "back":
        await _prompt_district_edit(call.message, state, session, region_code)
        return

    try:
        idx = int(raw)
        hromada_item = hromadas[idx]
    except Exception:
        await call.message.answer("Не вдалося розпізнати громаду. Спробуйте ще раз.")
        return

    await state.update_data(hromada=hromada_item.name, hromada_code=hromada_item.code)
    await _prompt_settlement_edit(call.message, state, session, region_code, district_code, hromada_item.code)


@router.callback_query(EditProfile.settlement, F.data.startswith("loc:s:"))
async def settlement_pick(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await call.answer()
    _, _, raw = call.data.split(":", 2)
    data = await state.get_data()
    settlements = data.get("settlement_options", [])
    region_code = data.get("region_code")
    district_code = data.get("district_code")
    hromada_code = data.get("hromada_code")

    if raw == "back":
        await _prompt_hromada_edit(call.message, state, session, region_code, district_code)
        return

    try:
        idx = int(raw)
        settlement_item = settlements[idx]
    except Exception:
        await call.message.answer("Не вдалося розпізнати населений пункт. Спробуйте ще раз.")
        return

    await state.update_data(settlement=settlement_item.name, settlement_code=settlement_item.code)
    await call.message.answer("Це місто чи село?", reply_markup=settlement_type_kb())
    await state.set_state(EditProfile.settlement_type)


@router.callback_query(EditProfile.settlement_type, F.data.startswith("loc:type:"))
async def settlement_type_pick(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await call.answer()
    _, _, value = call.data.split(":", 2)
    if value not in {"city", "village"}:
        await call.message.answer("Оберіть кнопку: місто чи село.", reply_markup=settlement_type_kb())
        return

    await state.update_data(settlement_type=value)
    await _save_location_and_finish(call.message, state, session)


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
