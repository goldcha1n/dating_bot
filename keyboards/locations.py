from typing import Optional

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def regions_kb(regions: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for idx, name in enumerate(regions):
        builder.button(text=name, callback_data=f"loc:r:{idx}")
    builder.button(text="Назад ↩️", callback_data="loc:r:back")
    builder.adjust(2)
    return builder.as_markup()


def districts_kb(districts: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for idx, name in enumerate(districts):
        builder.button(text=name, callback_data=f"loc:d:{idx}")
    builder.button(text="Без району", callback_data="loc:d:none")
    builder.button(text="Назад ↩️", callback_data="loc:d:back")
    builder.adjust(2)
    return builder.as_markup()


def hromadas_kb(hromadas: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for idx, name in enumerate(hromadas):
        builder.button(text=name, callback_data=f"loc:h:{idx}")
    builder.button(text="Назад ↩️", callback_data="loc:h:back")
    builder.adjust(2)
    return builder.as_markup()


def settlements_kb(settlements: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for idx, name in enumerate(settlements):
        builder.button(text=name, callback_data=f"loc:s:{idx}")
    builder.button(text="Назад ↩️", callback_data="loc:s:back")
    builder.adjust(2)
    return builder.as_markup()


def search_scope_kb(current: Optional[str] = None) -> InlineKeyboardMarkup:
    labels = {
        "settlement": "Тільки в цьому населеному пункті",
        "hromada": "У громаді",
        "district": "У районі",
        "region": "У області",
        "country": "По всій країні",
    }
    builder = InlineKeyboardBuilder()
    order = ["settlement", "hromada", "district", "region", "country"]
    for scope in order:
        label = labels[scope]
        if current == scope:
            label = f"✓ {label}"
        builder.button(text=label, callback_data=f"loc:scope:{scope}")
    builder.adjust(1)
    return builder.as_markup()
