"""Инициализация всех 13 агентов в БД"""
import asyncio
from core.database import engine, AsyncSessionLocal
from models.all_models import Base, Agent
from agents.all_agents import DIRECTOR_SYSTEM_PROMPT_V2
from agents.backend_dev_agent import BACKEND_DEV_SYSTEM_PROMPT

AGENT_CONFIGS = [
    {"id": "director",     "name": "Директор",             "role": "CEO / Оркестратор",    "provider": "deepseek", "model": "deepseek-reasoner", "prompt": DIRECTOR_SYSTEM_PROMPT_V2},
    {"id": "analyst",      "name": "Аналитик рынка",        "role": "Market Research",       "provider": "deepseek", "model": "deepseek-reasoner"},
    {"id": "pm",           "name": "Продуктовый менеджер",  "role": "Product Manager",       "provider": "deepseek", "model": "deepseek-reasoner"},
    {"id": "backend_dev",  "name": "Backend Dev",           "role": "Backend-разработчик",   "provider": "deepseek", "model": "deepseek-chat", "prompt": BACKEND_DEV_SYSTEM_PROMPT},
    {"id": "frontend_dev", "name": "Frontend Dev",          "role": "Frontend-разработчик",  "provider": "codex",    "model": "gpt-4o"},
    {"id": "ux_ui",        "name": "UX/UI Дизайнер",        "role": "UX/UI Designer",        "provider": "deepseek", "model": "deepseek-chat"},
    {"id": "qa",           "name": "QA-инженер",            "role": "Quality Assurance",     "provider": "deepseek", "model": "deepseek-chat"},
    {"id": "devops",       "name": "DevOps",                "role": "DevOps-инженер",        "provider": "deepseek", "model": "deepseek-chat"},
    {"id": "marketer",     "name": "Маркетолог",            "role": "Marketer",              "provider": "deepseek", "model": "deepseek-reasoner"},
    {"id": "copywriter",   "name": "Копирайтер",            "role": "Copywriter",            "provider": "deepseek", "model": "deepseek-chat"},
    {"id": "smm",          "name": "SMM-менеджер",          "role": "SMM Manager",           "provider": "deepseek", "model": "deepseek-chat"},
    {"id": "seo",          "name": "SEO-специалист",        "role": "SEO Specialist",        "provider": "deepseek", "model": "deepseek-chat"},
    {"id": "finance",      "name": "Финансовый аналитик",   "role": "Financial Analyst",     "provider": "deepseek", "model": "deepseek-chat"},
]

async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        for cfg in AGENT_CONFIGS:
            existing = await db.get(Agent, cfg["id"])
            if not existing:
                db.add(Agent(
                    id=cfg["id"], name=cfg["name"], role=cfg["role"],
                    status="idle", provider=cfg.get("provider", "deepseek"),
                    model=cfg.get("model", "deepseek-chat"),
                    system_prompt=cfg.get("prompt"), tools=[], config={},
                ))
                print(f"✅ {cfg['name']}")
            else:
                print(f"⏭️  {cfg['name']}")
        await db.commit()
    print("\n✅ Все 13 агентов готовы")

if __name__ == "__main__":
    asyncio.run(seed())
