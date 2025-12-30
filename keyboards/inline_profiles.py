from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def gender_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Парень"), KeyboardButton(text="Девушка")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def looking_for_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Парни"), KeyboardButton(text="Девушки")],
            [KeyboardButton(text="Любой")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def skip_about_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Пропустить")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def to_menu_inline_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="В меню", callback_data="noop:menu")
    return builder.as_markup()


def browse_kb(candidate_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❤️ Нравится", callback_data=f"browse:like:{candidate_user_id}"),
        InlineKeyboardButton(text="✖️ Пропустить", callback_data=f"browse:skip:{candidate_user_id}"),
    )
    builder.row(
        InlineKeyboardButton(
            text="🚩 Пожаловаться", callback_data=f"complaint:start:{candidate_user_id}"
        )
    )
    return builder.as_markup()


def profile_manage_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Имя", callback_data="profile:edit_name")
    builder.button(text="🎂 Возраст", callback_data="profile:edit_age")
    builder.button(text="⚧ Пол", callback_data="profile:edit_gender")
    builder.button(text="🎯 Ищу", callback_data="profile:edit_looking_for")
    builder.button(text="📍 Город", callback_data="profile:edit_city")
    builder.button(text="📝 О себе", callback_data="profile:edit_about")
    builder.button(text="📸 Фото", callback_data="profile:edit_photo")
    builder.button(text="🗑️ Удалить профиль", callback_data="profile:delete")
    builder.adjust(1)
    return builder.as_markup()


def confirm_delete_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Да, удалить", callback_data="profile_delete:yes"),
        InlineKeyboardButton(text="Отмена", callback_data="profile_delete:no"),
    )
    return builder.as_markup()


def like_notification_kb(from_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❤️ Взаимно", callback_data=f"inlike:like:{from_user_id}"),
        InlineKeyboardButton(text="✖️ Пропустить", callback_data=f"inlike:skip:{from_user_id}"),
    )
    return builder.as_markup()


def match_contact_kb(url: str, target_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📨 Написать", url=url),
        InlineKeyboardButton(text="🚩 Пожаловаться", callback_data=f"complaint:start:{target_user_id}"),
    )
    return builder.as_markup()


def matches_pager_kb(url: str, target_user_id: int, page: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📨 Написать", url=url),
        InlineKeyboardButton(text="🚩 Пожаловаться", callback_data=f"complaint:start:{target_user_id}"),
    )

    if total > 1:
        nav = []
        if page > 1:
            nav.append(InlineKeyboardButton(text="◀", callback_data=f"matches:page:{page-1}"))
        nav.append(InlineKeyboardButton(text=f"{page}/{total}", callback_data="noop:page"))
        if page < total:
            nav.append(InlineKeyboardButton(text="▶", callback_data=f"matches:page:{page+1}"))
        builder.row(*nav)

    return builder.as_markup()


def complaint_reasons_kb(target_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Спам", callback_data=f"complaint:reason:spam:{target_user_id}"),
        InlineKeyboardButton(text="Фейк", callback_data=f"complaint:reason:fake:{target_user_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="Оскорбления", callback_data=f"complaint:reason:obscene:{target_user_id}"),
        InlineKeyboardButton(text="Другое", callback_data=f"complaint:reason:other:{target_user_id}"),
    )
    return builder.as_markup()
