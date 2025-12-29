from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


# Тексты кнопок (используем константы, чтобы не дублировать строки в хендлерах)
BTN_BROWSE = "👀 Смотреть анкеты"
BTN_PROFILE = "👤 Моя анкета"
BTN_MATCHES = "❤️ Взаимные лайки"
BTN_SETTINGS = "⚙️ Настройки"


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_BROWSE)],
            [KeyboardButton(text=BTN_PROFILE), KeyboardButton(text=BTN_MATCHES)],
            [KeyboardButton(text=BTN_SETTINGS)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие…",
    )
