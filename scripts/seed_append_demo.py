from __future__ import annotations

import asyncio
import os
import random
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple

from sqlalchemy import func, select

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import ensure_runtime_paths  # noqa: E402
from db import create_engine, create_sessionmaker, init_db  # noqa: E402
from models import Like, Match, Photo, User  # noqa: E402
from utils.locations import get_locations  # noqa: E402

NEW_USERS = 100
LIKES_PER_USER = 50
MATCHES_PER_USER = 50
PHOTO_URL = "https://picsum.photos/seed/{seed}/800/800"

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


async def seed_users_with_photos(session, count: int, start_tg: int) -> List[int]:
    users: List[User] = []
    for i in range(count):
        gender = random.choice(["M", "F"])
        looking_for = random.choice(["M", "F", "A"])
        first, last, full_name = _pick_name(gender)
        about = _pick_about()
        tg_id = start_tg + i
        region, district, settlement = _pick_location()
        search_scope = random.choice(["settlement", "district", "region", "country"])

        user = User(
            tg_id=tg_id,
            username=f"user{tg_id}",
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
            settlement_type="city",
            search_scope=search_scope,
            about=about,
            search_global=search_scope != "settlement",
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
    return [u.id for u in users]


async def seed_likes(session, user_ids: Sequence[int], per_user: int) -> int:
    if len(user_ids) < 2 or per_user <= 0:
        return 0

    existing_pairs: Set[Tuple[int, int]] = {
        (row[0], row[1]) for row in (await session.execute(select(Like.from_user_id, Like.to_user_id))).all()
    }
    existing_counts: Dict[int, int] = {}
    for frm, _ in existing_pairs:
        existing_counts[frm] = existing_counts.get(frm, 0) + 1

    created = 0
    batch: List[Like] = []
    for user_id in user_ids:
        already = existing_counts.get(user_id, 0)
        remaining = max(per_user - already, 0)
        if remaining == 0:
            continue

        candidates = [uid for uid in user_ids if uid != user_id and (user_id, uid) not in existing_pairs]
        random.shuffle(candidates)
        for target_id in candidates[:remaining]:
            pair = (user_id, target_id)
            existing_pairs.add(pair)
            batch.append(Like(from_user_id=user_id, to_user_id=target_id, is_like=True))
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


async def seed_matches(session, user_ids: Sequence[int], per_user: int) -> int:
    if len(user_ids) < 2 or per_user <= 0:
        return 0

    def norm_pair(a: int, b: int) -> Tuple[int, int]:
        return (a, b) if a < b else (b, a)

    existing_pairs: Set[Tuple[int, int]] = {
        norm_pair(row[0], row[1]) for row in (await session.execute(select(Match.user1_id, Match.user2_id))).all()
    }
    counts: Dict[int, int] = {}
    for a, b in existing_pairs:
        counts[a] = counts.get(a, 0) + 1
        counts[b] = counts.get(b, 0) + 1

    created = 0
    batch: List[Match] = []
    attempts = 0
    max_attempts = len(user_ids) * per_user * 5

    while attempts < max_attempts:
        user_id = random.choice(user_ids)
        if counts.get(user_id, 0) >= per_user:
            attempts += 1
            continue

        target_id = random.choice(user_ids)
        if target_id == user_id:
            attempts += 1
            continue

        pair = norm_pair(user_id, target_id)
        if pair in existing_pairs:
            attempts += 1
            continue

        existing_pairs.add(pair)
        counts[user_id] = counts.get(user_id, 0) + 1
        counts[target_id] = counts.get(target_id, 0) + 1
        batch.append(Match(user1_id=pair[0], user2_id=pair[1]))

        if len(batch) >= 500:
            session.add_all(batch)
            await session.commit()
            created += len(batch)
            batch.clear()

        if all(counts.get(uid, 0) >= per_user for uid in user_ids):
            break

    if batch:
        session.add_all(batch)
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
        existing_count = (await session.execute(select(func.count()).select_from(User))).scalar_one()
        max_tg = (await session.execute(select(func.max(User.tg_id)))).scalar_one()
        start_tg = (max_tg or 1_000_000_000) + 10

        new_ids = await seed_users_with_photos(session, NEW_USERS, start_tg=start_tg)
        print(f"Inserted new users: {len(new_ids)} (total now {existing_count + len(new_ids)})")

        all_user_ids = [row[0] for row in (await session.execute(select(User.id))).all()]
        likes_created = await seed_likes(session, all_user_ids, per_user=LIKES_PER_USER)
        print(f"Inserted likes (up to {LIKES_PER_USER} per user): {likes_created}")

        matches_created = await seed_matches(session, all_user_ids, per_user=MATCHES_PER_USER)
        print(f"Inserted matches (up to {MATCHES_PER_USER} per user): {matches_created}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
