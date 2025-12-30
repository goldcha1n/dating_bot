from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def settings_kb(search_global: bool, active: bool, age_filter_enabled: bool) -> InlineKeyboardMarkup:
    city_mode = "🌍 У будь-якому місті" if search_global else "📍 Лише в моєму місті"
    active_mode = "🟢 Анкета видима" if active else "⏸️ Анкета на паузі"
    age_mode = "✅ Увімкнено" if age_filter_enabled else "❌ Вимкнено"

    builder = InlineKeyboardBuilder()
    builder.button(text=f"🔎 Пошук: {city_mode}", callback_data="settings:toggle_city")
    builder.button(text=f"🧾 Статус: {active_mode}", callback_data="settings:toggle_active")
    builder.button(text=f"🎂 Віковий фільтр: {age_mode}", callback_data="settings:toggle_age_filter")
    builder.adjust(1)
    return builder.as_markup()


def open_settings_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⚙️ Відкрити налаштування", callback_data="settings:open")
    return builder.as_markup()
