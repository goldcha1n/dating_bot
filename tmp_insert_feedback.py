import asyncio, random
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import get_settings
from models import Feedback, User

TEXTS = [
    "Доволен качеством сервиса.",
    "Нашёл пару, спасибо!",
    "Нужно улучшить скорость отклика.",
    "Есть идеи по новому фильтру поиска.",
    "Иногда падают фото при загрузке.",
    "Хотел бы больше подсказок в интерфейсе.",
    "Все работает стабильно.",
    "Проблема с уведомлениями о лайках.",
    "Нравится дизайн, продолжайте!",
    "Добавьте больше настроек приватности.",
]

async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        await session.execute(delete(Feedback))
        rows = (await session.execute(select(User.id, User.tg_id, User.username))).all()
        users = [{"id": r[0], "tg_id": r[1], "username": r[2]} for r in rows]
        if not users:
            print("No users; abort")
            return
        items = []
        for i in range(1000):
            u = random.choice(users)
            items.append(
                Feedback(
                    user_id=u["id"],
                    tg_id=u["tg_id"],
                    username=u["username"],
                    category=random.choice(["general", "issue", "idea", "other"]),
                    status=random.choice(["new", "in_progress", "done"]),
                    description=f"Автотест #{i+1}. {random.choice(TEXTS)}",
                )
            )
        session.add_all(items)
        await session.commit()
        print(f"Inserted {len(items)} feedback rows")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
