from __future__ import annotations

import asyncio
import os
import random
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from sqlalchemy import func, select

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import DEFAULT_DB_PATH, ensure_runtime_paths  # noqa: E402
from db import create_engine, create_sessionmaker, init_db  # noqa: E402
from models import Complaint, User  # noqa: E402

TOTAL_USERS = 10_000
TARGET_COMPLAINTS = 2_000
USER_BATCH_SIZE = 500
COMPLAINT_BATCH_SIZE = 500

FIRST_NAMES_M = [
    "Алексей",
    "Иван",
    "Дмитрий",
    "Сергей",
    "Никита",
    "Павел",
    "Фёдор",
    "Егор",
    "Роман",
    "Тимофей",
]
FIRST_NAMES_F = [
    "Анна",
    "Мария",
    "Екатерина",
    "Ольга",
    "Наталья",
    "Алина",
    "Виктория",
    "София",
    "Дарья",
    "Полина",
]
LAST_NAMES = [
    "Иванов",
    "Петров",
    "Сидоров",
    "Кузнецов",
    "Соколов",
    "Попов",
    "Лебедев",
    "Козлов",
    "Новиков",
    "Морозов",
]
CITIES = [
    "Киев",
    "Харьков",
    "Львов",
    "Одесса",
    "Днепр",
    "Запорожье",
    "Винница",
    "Кривой Рог",
    "Чернигов",
    "Полтава",
]
ABOUTS = [
    "Люблю прогулки и читать вечером.",
    "Ищу собеседника для путешествий.",
    "Готовлю лучше, чем мама сказала.",
    "Хочу больше узнавать людей и города.",
    "Музыка, бег и кофе — мои три кита.",
    "Ищу новые знакомства и интересные истории.",
    "Экспериментирую с фотографией и кулинарией.",
]
COMPLAINT_REASONS = [
    "Спам",
    "Фейк",
    "Оскорбления",
    "Неподходящий контент",
    "Подозрительное поведение",
    "Нарушение правил сообщества",
]


def _pick_about() -> str | None:
    choices: Sequence[str | None] = ABOUTS + [None, None, None]
    return random.choice(choices)


def _pick_name(gender: str) -> Tuple[str, str, str]:
    if gender == "M":
        first = random.choice(FIRST_NAMES_M)
    else:
        first = random.choice(FIRST_NAMES_F)
    last = random.choice(LAST_NAMES)
    full_name = f"{first} {last}"
    return first, last, full_name


async def seed_users(session, count: int, existing_count: int) -> List[int]:
    """Insert users in batches and return their IDs."""
    created_ids: List[int] = []
    batch: List[User] = []
    base_tg = 2_000_000_000 + existing_count * 2

    for i in range(count):
        gender = random.choice(["M", "F"])
        looking_for = random.choice(["M", "F", "A"])
        age = random.randint(16, 45) if gender == "M" else random.randint(18, 50)
        first, last, full_name = _pick_name(gender)
        username = f"user{base_tg + i}"

        user = User(
            tg_id=base_tg + i,
            username=username,
            first_name=first,
            last_name=last,
            name=full_name,
            age=age,
            age_filter_enabled=bool(random.getrandbits(1)),
            gender=gender,
            looking_for=looking_for,
            city=random.choice(CITIES),
            about=_pick_about(),
            search_global=bool(random.getrandbits(1)),
            active=True,
            is_banned=False,
        )
        batch.append(user)

        if len(batch) >= USER_BATCH_SIZE:
            session.add_all(batch)
            await session.flush()
            created_ids.extend([u.id for u in batch])
            await session.commit()
            batch.clear()

    if batch:
        session.add_all(batch)
        await session.flush()
        created_ids.extend([u.id for u in batch])
        await session.commit()

    return created_ids


async def seed_complaints(session, user_ids: Sequence[int], target_count: int) -> int:
    """Create complaints between random users, respecting unique constraint."""
    if len(user_ids) < 2:
        return 0

    existing_pairs = {
        (row[0], row[1])
        for row in (await session.execute(select(Complaint.reporter_user_id, Complaint.target_user_id))).all()
    }

    pairs: set[Tuple[int, int]] = set()
    attempts = 0
    max_attempts = target_count * 10

    while len(pairs) < target_count and attempts < max_attempts:
        reporter, target = random.sample(user_ids, 2)
        pair = (reporter, target)
        if pair in pairs or pair in existing_pairs:
            attempts += 1
            continue
        pairs.add(pair)

    batch: List[Complaint] = []
    created = 0
    for reporter, target in pairs:
        batch.append(
            Complaint(
                reporter_user_id=reporter,
                target_user_id=target,
                reason=random.choice(COMPLAINT_REASONS),
            )
        )
        if len(batch) >= COMPLAINT_BATCH_SIZE:
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
    db_url = os.getenv("DATABASE_URL") or f"sqlite+aiosqlite:///{DEFAULT_DB_PATH}"

    print(f"Using DB: {db_url}")
    engine = create_engine(db_url)
    await init_db(engine)
    Session = create_sessionmaker(engine)

    async with Session() as session:
        existing_users = (
            await session.execute(select(func.count()).select_from(User))
        ).scalar_one()
        to_create = max(TOTAL_USERS - existing_users, 0)
        print(f"Existing users: {existing_users}, need to add: {to_create}")

        new_ids: Iterable[int] = []
        if to_create:
            new_ids = await seed_users(session, to_create, existing_users)
            print(f"Inserted users: {len(list(new_ids))}")

        # Fetch full user id list (including newly created) for complaints.
        user_ids = [row[0] for row in (await session.execute(select(User.id))).all()]
        created_complaints = await seed_complaints(session, user_ids, TARGET_COMPLAINTS)
        print(f"Inserted complaints: {created_complaints}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
