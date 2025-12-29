from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(F.data.startswith("noop:"))
async def noop(call: CallbackQuery) -> None:
    # Used for small inline buttons that don't need action
    await call.answer()
