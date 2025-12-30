from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


# Тексти кнопок (використовуємо константи, щоб не дублювати рядки в хендлерах)
BTN_BROWSE = "👀 Перегляд анкет"
BTN_PROFILE = "👤 Моя анкета"
BTN_MATCHES = "❤️ Взаємні лайки"
BTN_SETTINGS = "⚙️ Налаштування"


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_BROWSE)],
            [KeyboardButton(text=BTN_PROFILE), KeyboardButton(text=BTN_MATCHES)],
            [KeyboardButton(text=BTN_SETTINGS)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Оберіть дію…",
    )
