from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def gender_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="👨 Мужчина"), KeyboardButton(text="👩 Женщина")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def looking_for_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👨 Мужчин"), KeyboardButton(text="👩 Женщин")],
            [KeyboardButton(text="🌍 Всех")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def skip_about_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⏭️ Пропустить")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def to_menu_inline_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 В меню", callback_data="noop:menu")
    return builder.as_markup()


def browse_kb(candidate_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❤️ Нравится", callback_data=f"browse:like:{candidate_user_id}"),
        InlineKeyboardButton(text="💤 Пропустить", callback_data=f"browse:skip:{candidate_user_id}"),
    )
    return builder.as_markup()


def profile_manage_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить имя", callback_data="profile:edit_name")
    builder.button(text="🎂 Изменить возраст", callback_data="profile:edit_age")
    builder.button(text="🚻 Изменить пол", callback_data="profile:edit_gender")
    builder.button(text="🎯 Изменить кого ищу", callback_data="profile:edit_looking_for")
    builder.button(text="🏙️ Изменить город", callback_data="profile:edit_city")
    builder.button(text="📝 Изменить «О себе»", callback_data="profile:edit_about")
    builder.button(text="🖼️ Изменить фото", callback_data="profile:edit_photo")
    builder.button(text="🗑️ Удалить анкету", callback_data="profile:delete")
    builder.adjust(1)
    return builder.as_markup()


def confirm_delete_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data="profile_delete:yes"),
        InlineKeyboardButton(text="❌ Нет", callback_data="profile_delete:no"),
    )
    return builder.as_markup()


def like_notification_kb(from_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❤️ Лайкнуть в ответ", callback_data=f"inlike:like:{from_user_id}"),
        InlineKeyboardButton(text="🙈 Не интересно", callback_data=f"inlike:skip:{from_user_id}"),
    )
    return builder.as_markup()


def match_contact_kb(url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✉️ Написать", url=url))
    return builder.as_markup()


def matches_pager_kb(url: str, page: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✉️ Написать", url=url))

    nav = []
    if total > 1:
        if page > 1:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"matches:page:{page-1}"))
        nav.append(InlineKeyboardButton(text=f"{page}/{total}", callback_data="noop:page"))
        if page < total:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"matches:page:{page+1}"))
        builder.row(*nav)

    return builder.as_markup()
