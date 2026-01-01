from __future__ import annotations

import asyncio
import csv
from pathlib import Path

from sqlalchemy import delete, insert

BASE_DIR = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(BASE_DIR))

from app.config import ensure_runtime_paths, get_settings  # noqa: E402
from db import create_engine, create_sessionmaker  # noqa: E402
from models import Base, UaLocation  # noqa: E402

CSV_PATH = BASE_DIR / "UA.csv"


async def load_csv() -> int:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"{CSV_PATH} not found")

    ensure_runtime_paths()
    settings = get_settings()

    engine = create_engine(settings.database_url)
    async_session = create_sessionmaker(engine)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    rows = []
    with CSV_PATH.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader, [])
        for row in reader:
            # Skip comment/garbage rows (e.g., long textual notes instead of UA codes).
            if not row or not row[0].strip().isdigit():
                continue
            if row[1] and not row[1].startswith("UA"):
                continue

            def short(val: str) -> str | None:
                val = (val or "").strip()
                if not val:
                    return None
                return val if len(val) <= 32 else None

            rows.append(
                {
                    "id": int(row[0]),
                    "level1": short(row[1]),
                    "level2": short(row[2]),
                    "level3": short(row[3]),
                    "level4": short(row[4]),
                    "level_extra": short(row[5]),
                    "category": short(row[6]),
                    "name": (row[7] or "").strip(),
                }
            )

    async with async_session() as session:
        await session.execute(delete(UaLocation))
        if rows:
            await session.execute(insert(UaLocation), rows)
        await session.commit()

    await engine.dispose()
    return len(rows)


async def main() -> None:
    total = await load_csv()
    print(f"Imported {total} ua_locations rows from {CSV_PATH.name}")


if __name__ == "__main__":
    asyncio.run(main())
