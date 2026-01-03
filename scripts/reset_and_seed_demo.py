from __future__ import annotations

import asyncio
import os
import random
import sys
from pathlib import Path
from typing import List, Sequence, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import ensure_runtime_paths
from db import create_engine, create_sessionmaker, init_db
from models import Base, Like, Match, Photo, User
from sqlalchemy import select
from utils.locations import get_locations

TOTAL_USERS = 100

MALE_NAMES = [
    "Ivan",
    "Dmytro",
    "Andriy",
    "Oleksii",
    "Sergiy",
    "Pavlo",
    "Roman",
    "Taras",
    "Yurii",
    "Vlad",
]

FEMALE_NAMES = [
    "Anna",
    "Iryna",
    "Olena",
    "Natalia",
    "Tetiana",
    "Maria",
    "Sofia",
    "Kateryna",
    "Oksana",
    "Larysa",
]

LAST_NAMES = [
    "Shevchenko",
    "Kovalenko",
    "Boyko",
    "Tkachenko",
    "Bondarenko",
    "Kravchenko",
    "Lysenko",
    "Polishchuk",
    "Melnyk",
    "Savchenko",
]

CITIES = [
    "Kyiv",
    "Lviv",
    "Odesa",
    "Kharkiv",
    "Dnipro",
    "Vinnytsia",
    "Ivano-Frankivsk",
    "Poltava",
    "Chernihiv",
    "Cherkasy",
]

ABOUTS = [
    "Love coffee, long walks, and road trips on weekends.",
    "Foodie at heart, exploring new places and cuisines.",
    "Book lover and music enthusiast looking for good company.",
    "Enjoy hiking, active weekends, and cozy movie nights.",
    "Tech geek, board games fan, and amateur cook.",
    "Sports, travel, and meaningful talks over tea.",
    "Fitness, nature, and spontaneous adventures.",
    "Photography, museums, and discovering hidden gems in the city.",
    "Dog person, park walks, and sunrises by the river.",
    "Learning languages, exploring cultures, and trying new coffee spots.",
]

PHOTO_URL = "https://picsum.photos/seed/{seed}/800/800"


def _pick_name(gender: str) -> Tuple[str, str, str]:
    first = random.choice(MALE_NAMES if gender == "M" else FEMALE_NAMES)
    last = random.choice(LAST_NAMES)
    return first, last, f"{first} {last}"


def _pick_about() -> str:
    return random.choice(ABOUTS)


def _pick_location() -> Tuple[str, str | None, str]:
    locations = get_locations()
    region = random.choice(list(locations.keys()))
    districts = list(locations[region].keys())
    district = random.choice(districts) if districts else None
    settlements = locations[region].get(district, []) if district else []
    settlement = random.choice(settlements) if settlements else region
    return region, district, settlement


async def seed_users_with_photos(session) -> int:
    users: List[User] = []
    base_tg = 1_000_000_000

    for i in range(TOTAL_USERS):
        gender = random.choice(["M", "F"])
        looking_for = random.choice(["M", "F", "A"])
        first, last, full_name = _pick_name(gender)
        about = _pick_about()
        region, district, settlement = _pick_location()
        search_scope = random.choice(["settlement", "hromada", "district", "region", "country"])

        user = User(
            tg_id=base_tg + i,
            username=f"user{base_tg + i}",
            first_name=first,
            last_name=last,
            name=full_name,
            age=random.randint(18, 45),
            age_filter_enabled=True,
            gender=gender,
            looking_for=looking_for,
            city=settlement,
            region=region,
            district=district,
            settlement=settlement,
            search_scope=search_scope,
            about=about,
            search_global=search_scope == "country",
            active=True,
            is_banned=False,
        )
        users.append(user)
        session.add(user)

    await session.flush()

    for user in users:
        seed = f"profile-{user.id or user.tg_id}"
        photo_url = PHOTO_URL.format(seed=seed)
        session.add(Photo(user_id=user.id, file_id=photo_url, is_main=True))

    await session.commit()
    return len(users)


async def seed_likes(session, user_ids: Sequence[int], per_user: int = 50) -> int:
    if len(user_ids) < 2:
        return 0

    created = 0
    batch: List[Like] = []
    for user_id in user_ids:
        targets = [uid for uid in user_ids if uid != user_id]
        random.shuffle(targets)
        for target_id in targets[: per_user]:
            batch.append(
                Like(
                    from_user_id=user_id,
                    to_user_id=target_id,
                    is_like=True,
                )
            )
            if len(batch) >= 1000:
                session.add_all(batch)
                await session.commit()
                created += len(batch)
                batch.clear()

    if batch:
        session.add_all(batch)
        await session.commit()
        created += len(batch)
    return created


async def seed_matches(session, user_ids: Sequence[int], target_pairs: int) -> int:
    if len(user_ids) < 2:
        return 0

    pairs: set[Tuple[int, int]] = set()
    attempts = 0
    max_attempts = target_pairs * 5

    while len(pairs) < target_pairs and attempts < max_attempts:
        u1, u2 = random.sample(user_ids, 2)
        pair = tuple(sorted((u1, u2)))
        if pair in pairs:
            attempts += 1
            continue
        pairs.add(pair)

    created = 0
    batch: List[Match] = []
    for u1, u2 in pairs:
        batch.append(Match(user1_id=u1, user2_id=u2))
        if len(batch) >= 500:
            session.add_all(batch)
            await session.commit()
            created += len(batch)
            batch.clear()

    if batch:
        session.add_all(batch)
        await session.commit()
        created += len(batch)

    return created


async def main() -> None:
    ensure_runtime_paths()

    db_url = os.getenv("DATABASE_URL") or "postgresql+asyncpg://appuser:strongpass@localhost:5432/dating_bot"
    print(f"Recreating DB at: {db_url}")
    engine = create_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    Session = create_sessionmaker(engine)

    async with Session() as session:
        inserted = await seed_users_with_photos(session)
        print(f"Inserted users: {inserted}")

        user_ids = [row[0] for row in (await session.execute(select(User.id))).all()]
        likes_created = await seed_likes(session, user_ids, per_user=50)
        print(f"Inserted likes: {likes_created}")

        match_pairs = len(user_ids) * 25  # ~50 matches per user (each pair counts twice)
        matches_created = await seed_matches(session, user_ids, match_pairs)
        print(f"Inserted matches: {matches_created}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
