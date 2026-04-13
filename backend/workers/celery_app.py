import asyncio
import sys
from pathlib import Path
from celery import Celery
from celery.schedules import crontab
from core.config import settings
from loguru import logger


# Celery worker/beat may start from a process cwd that does not include /app.
# Add the backend root explicitly so dynamic imports of sibling packages
# like `agents`, `core`, `models`, and `services` work reliably.
APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

celery_app = Celery(
    "devstudio",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["workers.celery_app"],
)
celery_app.conf.update(
    task_serializer="json", accept_content=["json"], result_serializer="json",
    timezone="Europe/Moscow", enable_utc=True, task_acks_late=True, worker_prefetch_multiplier=1,
)

ALL_AGENT_IDS = [
    "director", "analyst", "pm", "backend_dev", "frontend_dev",
    "ux_ui", "qa", "devops", "marketer", "copywriter", "smm", "seo", "finance",
]

celery_app.conf.beat_schedule = {
    **{
        f"{aid}-cycle": {
            "task": "workers.celery_app.run_agent_cycle",
            "schedule": 30.0,
            "args": [aid],
            "options": {"queue": "agents"},
        }
        for aid in ALL_AGENT_IDS
    },
    "daily-digest": {
        "task": "workers.celery_app.send_daily_digest",
        "schedule": crontab(hour=20, minute=0),
    },
    "check-stuck": {
        "task": "workers.celery_app.check_stuck_tasks",
        "schedule": crontab(minute=0),
    },
}


def _run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_agent(agent_id: str):
    from agents.backend_dev_agent import BackendDevAgent
    from agents.all_agents import (
        DirectorAgent, MarketAnalystAgent, ProductManagerAgent,
        FrontendDevAgent, UXUIAgent, QAAgent, DevOpsAgent,
        MarketerAgent, CopywriterAgent, SMMAgent, SEOAgent, FinanceAgent,
    )
    registry = {
        "director": DirectorAgent, "analyst": MarketAnalystAgent, "pm": ProductManagerAgent,
        "backend_dev": BackendDevAgent, "frontend_dev": FrontendDevAgent, "ux_ui": UXUIAgent,
        "qa": QAAgent, "devops": DevOpsAgent, "marketer": MarketerAgent,
        "copywriter": CopywriterAgent, "smm": SMMAgent, "seo": SEOAgent, "finance": FinanceAgent,
    }
    cls = registry.get(agent_id)
    return cls() if cls else None


@celery_app.task(name="workers.celery_app.run_agent_cycle", bind=True, max_retries=3)
def run_agent_cycle(self, agent_id: str):
    try:
        _run_async(_cycle(agent_id))
    except Exception as exc:
        logger.error(f"[{agent_id}] Celery error: {exc}")
        raise self.retry(exc=exc, countdown=60)


async def _cycle(agent_id: str):
    agent = _get_agent(agent_id)
    if not agent:
        logger.warning(f"Неизвестный агент: {agent_id}")
        return
    await agent.run()


@celery_app.task(name="workers.celery_app.send_daily_digest")
def send_daily_digest():
    _run_async(_daily_digest())


async def _daily_digest():
    from core.database import AsyncSessionLocal
    from sqlalchemy import select, func
    from datetime import datetime, timezone
    from models import Task, APIUsageLog
    from services.notification_service import notify
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    async with AsyncSessionLocal() as db:
        done = await db.scalar(select(func.count()).where(Task.status == "done", Task.updated_at >= today))
        inprog = await db.scalar(select(func.count()).where(Task.status == "in_progress"))
        cost = await db.scalar(select(func.sum(APIUsageLog.cost_usd)).where(APIUsageLog.created_at >= today))
        await notify(db=db, type="digest", priority="info",
            title="📊 Дайджест AI DevStudio",
            body=f"Завершено: {done or 0} | В работе: {inprog or 0} | AI расход: ${float(cost or 0):.4f}")


@celery_app.task(name="workers.celery_app.check_stuck_tasks")
def check_stuck_tasks():
    _run_async(_check_stuck())


async def _check_stuck():
    from core.database import AsyncSessionLocal
    from sqlalchemy import select
    from datetime import datetime, timezone, timedelta
    from models import Task
    from services.notification_service import notify
    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Task).where(Task.status == "in_progress", Task.updated_at < cutoff))
        for t in result.scalars().all():
            hours = round((datetime.now(timezone.utc) - t.updated_at).total_seconds() / 3600, 1)
            await notify(db=db, type="blocker", priority="high",
                title=f"Задача зависла: {t.title}",
                body=f"{t.assigned_to} не обновлял {hours}ч.",
                task_id=t.id, project_id=t.project_id)
