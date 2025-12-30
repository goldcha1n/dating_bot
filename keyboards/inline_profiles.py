from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def gender_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Хлопець"), KeyboardButton(text="Дівчина")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def looking_for_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Хлопці"), KeyboardButton(text="Дівчата")],
            [KeyboardButton(text="Будь-хто")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def skip_about_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Пропустити")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def to_menu_inline_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="У меню", callback_data="noop:menu")
    return builder.as_markup()


def browse_kb(candidate_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❤️ Подобається", callback_data=f"browse:like:{candidate_user_id}"),
        InlineKeyboardButton(text="✖️ Пропустити", callback_data=f"browse:skip:{candidate_user_id}"),
    )
    builder.row(
        InlineKeyboardButton(
            text="🚩 Поскаржитися", callback_data=f"complaint:start:{candidate_user_id}"
        )
    )
    return builder.as_markup()


def profile_manage_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Ім'я", callback_data="profile:edit_name")
    builder.button(text="🎂 Вік", callback_data="profile:edit_age")
    builder.button(text="⚧ Стать", callback_data="profile:edit_gender")
    builder.button(text="🎯 Кого шукаю", callback_data="profile:edit_looking_for")
    builder.button(text="📍 Місто", callback_data="profile:edit_city")
    builder.button(text="📝 Про себе", callback_data="profile:edit_about")
    builder.button(text="📸 Фото", callback_data="profile:edit_photo")
    builder.button(text="🗑️ Видалити профіль", callback_data="profile:delete")
    builder.adjust(1)
    return builder.as_markup()


def confirm_delete_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Так, видалити", callback_data="profile_delete:yes"),
        InlineKeyboardButton(text="Скасувати", callback_data="profile_delete:no"),
    )
    return builder.as_markup()


def like_notification_kb(from_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❤️ Взаємно", callback_data=f"inlike:like:{from_user_id}"),
        InlineKeyboardButton(text="✖️ Пропустити", callback_data=f"inlike:skip:{from_user_id}"),
    )
    return builder.as_markup()


def match_contact_kb(url: str, target_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📨 Написати", url=url),
        InlineKeyboardButton(text="🚩 Поскаржитися", callback_data=f"complaint:start:{target_user_id}"),
    )
    return builder.as_markup()


def matches_pager_kb(url: str, target_user_id: int, page: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📨 Написати", url=url),
        InlineKeyboardButton(text="🚩 Поскаржитися", callback_data=f"complaint:start:{target_user_id}"),
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
        InlineKeyboardButton(text="Образи", callback_data=f"complaint:reason:obscene:{target_user_id}"),
        InlineKeyboardButton(text="Інше", callback_data=f"complaint:reason:other:{target_user_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="Скасувати", callback_data="complaint:cancel"),
    )
    return builder.as_markup()
