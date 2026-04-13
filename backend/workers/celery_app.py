import asyncio
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init, worker_process_shutdown, worker_ready
from core.config import settings
from loguru import logger

celery_app = Celery(
    "devstudio",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["workers.celery_app"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=3600,
    task_time_limit=3660,
)

ALL_AGENT_IDS = [
    "director",
    "analyst",
    "pm",
    "backend_dev",
    "frontend_dev",
    "ux_ui",
    "qa",
    "devops",
    "marketer",
    "copywriter",
    "smm",
    "seo",
    "finance",
]

celery_app.conf.beat_schedule = {
    "director-cycle": {
        "task": "workers.celery_app.run_agent_cycle",
        "schedule": 60.0,
        "args": ["director"],
        "options": {"queue": "agents"},
    },
    **{
        f"{agent_id}-cycle": {
            "task": "workers.celery_app.run_agent_cycle",
            "schedule": 120.0,
            "args": [agent_id],
            "options": {"queue": "agents"},
        }
        for agent_id in ALL_AGENT_IDS
        if agent_id != "director"
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


_worker_loop: asyncio.AbstractEventLoop | None = None


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    global _worker_loop

    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()

    asyncio.set_event_loop(_worker_loop)
    return _worker_loop


def _run_async(coro):
    loop = _get_worker_loop()
    return loop.run_until_complete(coro)


@worker_process_init.connect
def _init_worker_loop(**_kwargs):
    _get_worker_loop()


@worker_process_shutdown.connect
def _shutdown_worker_loop(**_kwargs):
    global _worker_loop

    if _worker_loop is None or _worker_loop.is_closed():
        return

    try:
        _worker_loop.run_until_complete(_worker_loop.shutdown_asyncgens())
    except Exception as exc:
        logger.warning(f"Failed to shutdown async generators cleanly: {exc}")
    finally:
        _worker_loop.close()
        _worker_loop = None


@worker_ready.connect
def _start_event_consumer(sender=None, **_kwargs):
    try:
        from workers.event_consumer import setup_event_consumer

        setup_event_consumer()
        logger.info("[Celery] Event consumer started")
    except Exception as exc:
        logger.error(f"[Celery] Event consumer failed to start: {exc}")


def _get_agent(agent_id: str):
    from agents.backend_dev_agent import BackendDevAgent
    from agents.all_agents import (
        CopywriterAgent,
        DevOpsAgent,
        DirectorAgent,
        FinanceAgent,
        FrontendDevAgent,
        MarketerAgent,
        MarketAnalystAgent,
        ProductManagerAgent,
        QAAgent,
        SEOAgent,
        SMMAgent,
        UXUIAgent,
    )

    registry = {
        "director": DirectorAgent,
        "analyst": MarketAnalystAgent,
        "pm": ProductManagerAgent,
        "backend_dev": BackendDevAgent,
        "frontend_dev": FrontendDevAgent,
        "ux_ui": UXUIAgent,
        "qa": QAAgent,
        "devops": DevOpsAgent,
        "marketer": MarketerAgent,
        "copywriter": CopywriterAgent,
        "smm": SMMAgent,
        "seo": SEOAgent,
        "finance": FinanceAgent,
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
    from core.redis import get_redis

    lock_key = f"agent_cycle_lock:{agent_id}"
    redis = await get_redis()
    lock_acquired = await redis.set(lock_key, "1", ex=600, nx=True)
    if not lock_acquired:
        logger.debug(f"[{agent_id}] Skip cycle because lock is already held")
        return

    try:
        agent = _get_agent(agent_id)
        if not agent:
            logger.warning(f"Unknown agent: {agent_id}")
            return
        await agent.run()
    finally:
        await redis.delete(lock_key)


@celery_app.task(name="workers.celery_app.send_daily_digest")
def send_daily_digest():
    _run_async(_daily_digest())


async def _daily_digest():
    from core.database import AsyncSessionLocal
    from datetime import datetime, timezone
    from models import APIUsageLog, Task
    from services.notification_service import notify
    from sqlalchemy import func, select

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    async with AsyncSessionLocal() as db:
        done = await db.scalar(select(func.count()).where(Task.status == "done", Task.updated_at >= today))
        in_progress = await db.scalar(select(func.count()).where(Task.status == "in_progress"))
        cost = await db.scalar(select(func.sum(APIUsageLog.cost_usd)).where(APIUsageLog.created_at >= today))
        await notify(
            db=db,
            type="digest",
            priority="info",
            title="AI DevStudio Daily Digest",
            body=f"Done: {done or 0} | In progress: {in_progress or 0} | AI cost: ${float(cost or 0):.4f}",
        )


@celery_app.task(name="workers.celery_app.check_stuck_tasks")
def check_stuck_tasks():
    _run_async(_check_stuck())


async def _check_stuck():
    from core.database import AsyncSessionLocal
    from datetime import datetime, timedelta, timezone
    from models import Task
    from services.notification_service import notify
    from sqlalchemy import select

    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Task).where(Task.status == "in_progress", Task.updated_at < cutoff))
        for task in result.scalars().all():
            hours = round((datetime.now(timezone.utc) - task.updated_at).total_seconds() / 3600, 1)
            await notify(
                db=db,
                type="blocker",
                priority="high",
                title=f"Task appears stuck: {task.title}",
                body=f"{task.assigned_to} has not updated it for {hours}h.",
                task_id=task.id,
                project_id=task.project_id,
            )
