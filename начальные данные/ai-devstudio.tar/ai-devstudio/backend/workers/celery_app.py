import asyncio
from celery import Celery
from celery.schedules import crontab
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
    task_routes={
        "workers.celery_app.run_agent_cycle": {"queue": "agents"},
        "workers.celery_app.send_daily_digest": {"queue": "default"},
    },
)

# ── Расписание (Celery Beat) ──────────────────────────

celery_app.conf.beat_schedule = {
    # Проверка задач каждые 30 секунд
    "director-cycle": {
        "task": "workers.celery_app.run_agent_cycle",
        "schedule": 30.0,
        "args": ["director"],
        "options": {"queue": "agents"},
    },
    "backend-dev-cycle": {
        "task": "workers.celery_app.run_agent_cycle",
        "schedule": 30.0,
        "args": ["backend_dev"],
        "options": {"queue": "agents"},
    },
    # Ежедневный дайджест в 20:00 МСК
    "daily-digest": {
        "task": "workers.celery_app.send_daily_digest",
        "schedule": crontab(hour=20, minute=0),
        "options": {"queue": "default"},
    },
    # Проверка зависших задач каждый час
    "check-stuck-tasks": {
        "task": "workers.celery_app.check_stuck_tasks",
        "schedule": crontab(minute=0),
        "options": {"queue": "default"},
    },
}


def _run_async(coro):
    """Запустить async-функцию из синхронного Celery worker"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── ЗАДАЧИ ───────────────────────────────────────────

@celery_app.task(name="workers.celery_app.run_agent_cycle", bind=True, max_retries=3)
def run_agent_cycle(self, agent_id: str):
    """
    Главный цикл агента.
    Запускается по расписанию и при ручном trigger.
    """
    logger.info(f"Celery: запуск цикла агента {agent_id}")
    try:
        _run_async(_agent_cycle(agent_id))
    except Exception as exc:
        logger.error(f"Celery: ошибка цикла {agent_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


async def _agent_cycle(agent_id: str):
    from agents.director_agent import DirectorAgent
    from agents.backend_dev_agent import BackendDevAgent

    agents_map = {
        "director": DirectorAgent,
        "backend_dev": BackendDevAgent,
    }

    AgentClass = agents_map.get(agent_id)
    if not AgentClass:
        logger.warning(f"Неизвестный agent_id: {agent_id}")
        return

    agent = AgentClass()
    await agent.run()


@celery_app.task(name="workers.celery_app.send_daily_digest")
def send_daily_digest():
    """Ежедневный дайджест владельцу"""
    logger.info("Celery: отправка дайджеста")
    _run_async(_do_daily_digest())


async def _do_daily_digest():
    from core.database import AsyncSessionLocal
    from sqlalchemy import select, func
    from datetime import datetime, timezone
    from models import Task, APIUsageLog
    from services.notification_service import notify

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    async with AsyncSessionLocal() as db:
        tasks_done = await db.scalar(
            select(func.count()).where(
                Task.status == "done",
                Task.updated_at >= today_start,
            )
        )
        tasks_in_progress = await db.scalar(
            select(func.count()).where(Task.status == "in_progress")
        )
        ai_cost = await db.scalar(
            select(func.sum(APIUsageLog.cost_usd)).where(
                APIUsageLog.created_at >= today_start
            )
        )

        body = (
            f"Задач завершено сегодня: {tasks_done or 0}\n"
            f"Задач в работе: {tasks_in_progress or 0}\n"
            f"Расход на AI сегодня: ${float(ai_cost or 0):.4f}"
        )

        await notify(
            db=db,
            type="digest",
            priority="info",
            title="📊 Ежедневный дайджест AI DevStudio",
            body=body,
        )


@celery_app.task(name="workers.celery_app.check_stuck_tasks")
def check_stuck_tasks():
    """Найти задачи, зависшие более 2 часов"""
    logger.info("Celery: проверка зависших задач")
    _run_async(_do_check_stuck())


async def _do_check_stuck():
    from core.database import AsyncSessionLocal
    from sqlalchemy import select
    from datetime import datetime, timezone, timedelta
    from models import Task
    from services.notification_service import notify

    two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Task).where(
                Task.status == "in_progress",
                Task.updated_at < two_hours_ago,
            )
        )
        stuck = result.scalars().all()

        for task in stuck:
            hours = round((datetime.now(timezone.utc) - task.updated_at).total_seconds() / 3600, 1)
            await notify(
                db=db,
                type="blocker",
                priority="high",
                title=f"Задача завислa: {task.title}",
                body=f"Задача [{task.assigned_to}] не обновлялась {hours}ч.",
                task_id=task.id,
                project_id=task.project_id,
            )
