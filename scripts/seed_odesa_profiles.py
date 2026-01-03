from __future__ import annotations

import asyncio
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import ensure_runtime_paths  # noqa: E402
from db import create_engine, create_sessionmaker, init_db  # noqa: E402
from models import Photo, UaLocation, User  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

TARGET_USERS = 10_000
REGION_CODE = "UA51000000000030770"
DISTRICT_CATEGORIES = {"P"}
HROMADA_CATEGORIES = {"H"}
SETTLEMENT_CATEGORIES = {"C", "M", "T", "X", "B", "K", "潜"}

MALE_NAMES = ["Олег", "Сергій", "Павло", "Ігор", "Дмитро", "Юрій", "Тарас", "Андрій"]
FEMALE_NAMES = ["Олена", "Ірина", "Тетяна", "Анна", "Наталія", "Марія", "Катерина", "Оксана"]
LAST_NAMES = ["Шевченко", "Коваль", "Ткачук", "Бойко", "Кравченко", "Поліщук", "Лисенко", "Мельник"]
ABOUTS = [
    "Люблю море, каву та прогулянки вздовж узбережжя.",
    "Ціную відвертість і гарне почуття гумору.",
    "Вихідні — подорожі та нові місця, будні — робота і спорт.",
    "Шукаю цікавих людей для спілкування та нових ідей.",
    "Захоплююсь кулінарією, кіно і настільними іграми.",
    "Люблю читати, бігати та відкривати нові кав’ярні.",
    "Пишу музику та обожнюю концерти.",
    "Хочу більше подорожувати Україною.",
]


@dataclass
class SettRecord:
    name: str
    district: Optional[str]
    hromada: Optional[str]


async def load_locations(session) -> Tuple[str, List[SettRecord]]:
    """Load region name + all settlements for Odesa oblast with district/hromada names."""
    res_region = await session.execute(
        select(UaLocation.name).where(UaLocation.level1 == REGION_CODE, UaLocation.category == "O")
    )
    region_name = (res_region.scalar_one_or_none() or "Одеська").strip()
    # District names
    res_d = await session.execute(
        select(UaLocation.level2, UaLocation.name).where(
            UaLocation.level1 == REGION_CODE, UaLocation.category.in_(DISTRICT_CATEGORIES)
        )
    )
    district_by_code: Dict[str, str] = {row[0]: row[1] for row in res_d if row[0] and row[1]}

    # Hromada names
    res_h = await session.execute(
        select(UaLocation.level3, UaLocation.name).where(
            UaLocation.level1 == REGION_CODE, UaLocation.category.in_(HROMADA_CATEGORIES)
        )
    )
    hromada_by_code: Dict[str, str] = {row[0]: row[1] for row in res_h if row[0] and row[1]}

    # Settlements
    res_s = await session.execute(
        select(UaLocation.level2, UaLocation.level3, UaLocation.name)
        .where(
            UaLocation.level1 == REGION_CODE,
            UaLocation.category.in_(SETTLEMENT_CATEGORIES),
        )
    )

    settlements: List[SettRecord] = []
    for level2, level3, name in res_s:
        if not name:
            continue
        district = district_by_code.get(level2 or "")
        hromada = hromada_by_code.get(level3 or "")
        settlements.append(SettRecord(name=name.strip(), district=district, hromada=hromada))
    random.shuffle(settlements)
    return region_name, settlements


def pick_name(gender: str) -> Tuple[str, str, str]:
    first = random.choice(MALE_NAMES if gender == "M" else FEMALE_NAMES)
    last = random.choice(LAST_NAMES)
    return first, last, f"{first} {last}"


def pick_about() -> Optional[str]:
    return random.choice(ABOUTS + [None, None])


def pick_scope() -> str:
    # Невелика перевага локальних зон
    scopes = ["settlement"] * 4 + ["hromada"] * 3 + ["district"] * 2 + ["region", "country"]
    return random.choice(scopes)


async def seed_users(session, region_name: str, settlements: Sequence[SettRecord], count: int, start_tg: int) -> int:
    batch: List[User] = []
    created = 0

    if not settlements:
        raise RuntimeError("Не знайдено населених пунктів Одеської області")

    for i in range(count):
        gender = random.choice(["M", "F"])
        looking_for = random.choice(["M", "F", "A"])
        first, last, full_name = pick_name(gender)
        about = pick_about()
        settlement = settlements[i % len(settlements)]
        scope = pick_scope()

        tg_id = start_tg + i
        username = f"odesa{tg_id}"
        search_global = scope == "country"

        user = User(
            tg_id=tg_id,
            username=username,
            first_name=first,
            last_name=last,
            name=full_name,
            age=random.randint(18, 50),
            age_filter_enabled=True,
            gender=gender,
            looking_for=looking_for,
            city=settlement.name,
            region=region_name,
            district=settlement.district,
            hromada=settlement.hromada,
            settlement=settlement.name,
            search_scope=scope,
            about=about,
            search_global=search_global,
            active=True,
            is_banned=False,
        )
        batch.append(user)

        if len(batch) >= 500:
            session.add_all(batch)
            await session.flush()
            for u in batch:
                photo_seed = f"odesa-{u.tg_id}"
                session.add(Photo(user_id=u.id, file_id=f"https://picsum.photos/seed/{photo_seed}/600/600", is_main=True))
            await session.commit()
            created += len(batch)
            batch.clear()

    if batch:
        session.add_all(batch)
        await session.flush()
        for u in batch:
            photo_seed = f"odesa-{u.tg_id}"
            session.add(Photo(user_id=u.id, file_id=f"https://picsum.photos/seed/{photo_seed}/600/600", is_main=True))
        await session.commit()
        created += len(batch)

    return created


async def main() -> None:
    ensure_runtime_paths()
    db_url = os.getenv("DATABASE_URL") or "postgresql+asyncpg://appuser:strongpass@localhost:5432/dating_bot"
    print(f"Using DB: {db_url}")
    engine = create_engine(db_url)
    await init_db(engine)
    Session = create_sessionmaker(engine)

    async with Session() as session:
        region_name, settlements = await load_locations(session)
        print(f"Loaded settlements in Odesa oblast: {len(settlements)}, region name='{region_name}'")
        max_tg = (await session.execute(select(func.max(User.tg_id)))).scalar_one()
        start_tg = (max_tg or 2_000_000_000) + 10
        created = await seed_users(session, region_name, settlements, TARGET_USERS, start_tg=start_tg)
        print(f"Inserted users: {created}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
