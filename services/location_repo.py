from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import UaLocation

DISTRICT_CATEGORIES = {"P"}
HROMADA_CATEGORIES = {"H"}
SETTLEMENT_CATEGORIES = {"C", "M", "T", "X", "B", "K", "С"}


@dataclass
class LocationItem:
    code: str
    name: str
    category: str


def _normalize_items(rows: Iterable[tuple[str | None, str | None, str | None]]) -> List[LocationItem]:
    items: list[LocationItem] = []
    seen: set[str] = set()
    for code, name, category in rows:
        if not code or not name:
            continue
        key = code
        if key in seen:
            continue
        seen.add(key)
        items.append(LocationItem(code=code, name=name.strip(), category=category or ""))
    items.sort(key=lambda item: item.name)
    return items


class LocationRepository:
    """Lightweight read-only repo over ua_locations table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_regions(self) -> List[LocationItem]:
        stmt = select(UaLocation.level1, UaLocation.name, UaLocation.category).where(UaLocation.category == "O")
        res = await self.session.execute(stmt)
        return _normalize_items(res.all())

    async def list_districts(self, region_code: str) -> List[LocationItem]:
        if not region_code:
            return []
        stmt = (
            select(UaLocation.level2, UaLocation.name, UaLocation.category)
            .where(UaLocation.level1 == region_code, UaLocation.category.in_(DISTRICT_CATEGORIES))
        )
        res = await self.session.execute(stmt)
        return _normalize_items(res.all())

    async def list_hromadas(self, region_code: str, district_code: str | None) -> List[LocationItem]:
        if not region_code or not district_code:
            return []
        stmt = (
            select(UaLocation.level3, UaLocation.name, UaLocation.category)
            .where(
                UaLocation.level1 == region_code,
                UaLocation.level2 == district_code,
                UaLocation.category.in_(HROMADA_CATEGORIES),
            )
        )
        res = await self.session.execute(stmt)
        return _normalize_items(res.all())

    async def list_settlements(
        self,
        region_code: str,
        district_code: str | None,
        hromada_code: str | None,
        categories: set[str] | None = None,
    ) -> List[LocationItem]:
        if not region_code:
            return []

        cats = categories or SETTLEMENT_CATEGORIES
        conditions = [UaLocation.level1 == region_code, UaLocation.category.in_(cats)]
        if district_code:
            conditions.append(UaLocation.level2 == district_code)
        if hromada_code:
            conditions.append(UaLocation.level3 == hromada_code)

        stmt = select(UaLocation.level4, UaLocation.name, UaLocation.category).where(*conditions)
        res = await self.session.execute(stmt)
        return _normalize_items(res.all())

    async def list_settlements_by_district(
        self, region_code: str, district_code: str | None, categories: set[str] | None = None
    ) -> List[LocationItem]:
        """Fallback if there are no hromadas for the district."""
        return await self.list_settlements(region_code, district_code, None, categories=categories)
