"""
Redis event consumer for event-driven agent wakeups.
"""
from __future__ import annotations

import asyncio
import json
import threading

from loguru import logger


CHANNEL = "task_events"


async def _on_comment_added(data: dict):
    assigned_to = data.get("assigned_to")
    author = data.get("author")
    if not assigned_to or author == assigned_to:
        return
    logger.info(f"[EventConsumer] comment_added -> trigger {assigned_to}")
    _trigger_agent(assigned_to)


async def _on_task_assigned(data: dict):
    assigned_to = data.get("assigned_to")
    if not assigned_to:
        return
    logger.info(f"[EventConsumer] task_assigned -> trigger {assigned_to}")
    _trigger_agent(assigned_to)


async def _on_subtask_completed(data: dict):
    if not data.get("parent_task_id"):
        return
    logger.info("[EventConsumer] subtask_completed -> trigger director")
    _trigger_agent("director")


async def _on_approval_given(data: dict):
    task_id = data.get("task_id")
    if not task_id:
        return

    try:
        from core.database import AsyncSessionLocal
        from models import Task
        from sqlalchemy import update

        async with AsyncSessionLocal() as db:
            task = await db.get(Task, task_id)
            if not task:
                return

            if task.status == "awaiting_approval":
                await db.execute(update(Task).where(Task.id == task_id).values(status="in_progress"))
                await db.commit()
                task.status = "in_progress"

            target_agent = task.assigned_to or "director"
            logger.info(f"[EventConsumer] approval_given -> trigger {target_agent}")
            _trigger_agent(target_agent)
    except Exception as exc:
        logger.error(f"approval_given handler error: {exc}")


EVENT_HANDLERS = {
    "comment_added": _on_comment_added,
    "task_assigned": _on_task_assigned,
    "subtask_completed": _on_subtask_completed,
    "approval_given": _on_approval_given,
}


def _trigger_agent(agent_id: str):
    try:
        from workers.celery_app import run_agent_cycle

        job = run_agent_cycle.apply_async(args=[agent_id], countdown=0)
        logger.debug(f"[EventConsumer] queued job {job.id} for {agent_id}")
    except Exception as exc:
        logger.warning(f"[EventConsumer] Celery unavailable: {exc}")


async def run_event_consumer():
    logger.info(f"[EventConsumer] Starting on channel '{CHANNEL}'")

    while True:
        try:
            from core.redis import get_redis

            redis = await get_redis()
            pubsub = redis.pubsub()
            await pubsub.subscribe(CHANNEL)
            logger.info(f"[EventConsumer] Subscribed to {CHANNEL}")

            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue

                try:
                    data = json.loads(message["data"])
                    event_name = data.get("event")
                    handler = EVENT_HANDLERS.get(event_name)
                    if handler:
                        await handler(data)
                    else:
                        logger.debug(f"[EventConsumer] Unknown event: {event_name}")
                except json.JSONDecodeError:
                    logger.warning(f"[EventConsumer] Invalid JSON: {message.get('data')}")
                except Exception as exc:
                    logger.error(f"[EventConsumer] Handler error: {exc}")
        except asyncio.CancelledError:
            logger.info("[EventConsumer] Stopped")
            break
        except Exception as exc:
            logger.error(f"[EventConsumer] Connection error: {exc}. Retry in 5s")
            await asyncio.sleep(5)


def setup_event_consumer():
    def _runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_event_consumer())
        finally:
            loop.close()

    thread = threading.Thread(target=_runner, daemon=True, name="event-consumer")
    thread.start()
    logger.info("[EventConsumer] Background thread started")
