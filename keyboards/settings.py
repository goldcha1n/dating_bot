from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def settings_kb(search_global: bool, active: bool, age_filter_enabled: bool) -> InlineKeyboardMarkup:
    city_mode = "🌍 В любом городе" if search_global else "📍 Только в моём городе"
    active_mode = "🟢 Анкета видна" if active else "⏸️ Анкета на паузе"
    age_mode = "✅ Включён" if age_filter_enabled else "❌ Выключен"

    builder = InlineKeyboardBuilder()
    builder.button(text=f"🔎 Поиск: {city_mode}", callback_data="settings:toggle_city")
    builder.button(text=f"🧾 Статус: {active_mode}", callback_data="settings:toggle_active")
    builder.button(text=f"🎂 Возрастной фильтр: {age_mode}", callback_data="settings:toggle_age_filter")
    builder.adjust(1)
    return builder.as_markup()


def open_settings_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⚙️ Открыть настройки", callback_data="settings:open")
    return builder.as_markup()
