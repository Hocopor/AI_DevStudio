"""
Начальные данные — создаёт агентов при первом запуске.
Запуск: python seed.py
"""
import asyncio
from core.database import engine, AsyncSessionLocal
from models.all_models import Base, Agent
from agents.director_agent import DIRECTOR_SYSTEM_PROMPT
from agents.backend_dev_agent import BACKEND_DEV_SYSTEM_PROMPT


INITIAL_AGENTS = [
    {
        "id": "director",
        "name": "Директор",
        "role": "CEO / Оркестратор",
        "status": "idle",
        "provider": "deepseek",
        "model": "deepseek-reasoner",
        "system_prompt": DIRECTOR_SYSTEM_PROMPT,
        "tools": ["create_subtask", "comment_task", "update_task_status", "update_live_plan", "request_approval", "web_search"],
    },
    {
        "id": "backend_dev",
        "name": "Backend Dev",
        "role": "Backend-разработчик",
        "status": "idle",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "system_prompt": BACKEND_DEV_SYSTEM_PROMPT,
        "tools": ["comment_task", "update_task_status", "update_live_plan", "web_search", "write_file", "execute_code"],
    },
]


async def seed():
    # Создать таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        for data in INITIAL_AGENTS:
            existing = await db.get(Agent, data["id"])
            if not existing:
                agent = Agent(**data)
                db.add(agent)
                print(f"✅ Создан агент: {data['name']}")
            else:
                print(f"⏭️  Агент уже существует: {data['name']}")
        await db.commit()

    print("\n✅ Seed завершён")


if __name__ == "__main__":
    asyncio.run(seed())
