"""
Communication tools for agents.
"""
from __future__ import annotations

import json
import uuid

from loguru import logger

from agents.tools.registry import ToolParam, ToolResult, tool


async def _publish_task_event(event: dict):
    try:
        from core.redis import get_redis

        redis = await get_redis()
        await redis.publish("task_events", json.dumps(event, ensure_ascii=False))
    except Exception as exc:
        logger.debug(f"Redis publish error: {exc}")


async def _do_comment(task_id: str, author: str, content: str) -> bool:
    try:
        from core.database import AsyncSessionLocal
        from models import Task, TaskComment
        from services.ws_manager import ws_manager

        async with AsyncSessionLocal() as db:
            task = await db.get(Task, task_id)
            if not task:
                return False

            comment = TaskComment(
                id=str(uuid.uuid4()),
                task_id=task_id,
                author=author,
                content=content,
                attachments=[],
            )
            db.add(comment)
            await db.commit()
            project_id = task.project_id
            assigned_to = task.assigned_to

        await ws_manager.broadcast(
            {
                "event": "task_comment_added",
                "task_id": task_id,
                "author": author,
                "project_id": project_id,
            }
        )
        await _publish_task_event(
            {
                "event": "comment_added",
                "task_id": task_id,
                "assigned_to": assigned_to,
                "author": author,
                "project_id": project_id,
            }
        )
        return True
    except Exception as exc:
        logger.error(f"_do_comment error: {exc}")
        return False


@tool(
    name="comment_task",
    description="Add a comment to the current task with progress, questions, or findings.",
    params=[ToolParam("content", "string", "Comment text in markdown.", required=True)],
)
async def comment_task(content: str, ctx) -> ToolResult:
    if await _do_comment(ctx.task_id, ctx.agent_id, content):
        return ToolResult(ok=True, output="Comment added.")
    return ToolResult(ok=False, output="", error="Could not add comment.")


@tool(
    name="ask_director",
    description="Ask the director for clarification when you are blocked or missing context.",
    params=[ToolParam("question", "string", "Concrete question for the director.", required=True)],
)
async def ask_director(question: str, ctx) -> ToolResult:
    message = f"Need director clarification:\n\n{question}"
    ok = await _do_comment(ctx.task_id, ctx.agent_id, message)
    if ok:
        return ToolResult(ok=True, output="Question sent to director via task comments.")
    return ToolResult(ok=False, output="", error="Could not send question to director.")


@tool(
    name="mark_task_done",
    description="Finish the current task when all required work is complete.",
    params=[ToolParam("result", "string", "Final task result summary.", required=True)],
)
async def mark_task_done(result: str, ctx) -> ToolResult:
    return ToolResult(ok=True, output="Task marked complete in memory.", data={"result": result})


@tool(
    name="notify_owner",
    description="Notify the owner about a blocker, risk, or important milestone.",
    params=[
        ToolParam("title", "string", "Short notification title.", required=True),
        ToolParam("body", "string", "Notification body.", required=True),
        ToolParam("priority", "string", "Priority.", required=False, enum=["info", "high", "critical"]),
    ],
)
async def notify_owner(title: str, body: str, ctx, priority: str = "info") -> ToolResult:
    try:
        from core.database import AsyncSessionLocal
        from services.notification_service import notify

        async with AsyncSessionLocal() as db:
            await notify(
                db=db,
                type="agent_update",
                priority=priority,
                title=title,
                body=body,
                task_id=ctx.task_id,
                project_id=ctx.project_id or None,
            )
        return ToolResult(ok=True, output="Owner notified.")
    except Exception as exc:
        return ToolResult(ok=False, output="", error=str(exc))


@tool(
    name="request_approval",
    description="Pause the current task and ask the owner for approval or a decision.",
    params=[ToolParam("question", "string", "Approval request or decision question.", required=True)],
)
async def request_approval(question: str, ctx) -> ToolResult:
    try:
        from core.database import AsyncSessionLocal
        from models import Task
        from services.notification_service import notify
        from services.ws_manager import ws_manager
        from sqlalchemy import update

        async with AsyncSessionLocal() as db:
            await db.execute(update(Task).where(Task.id == ctx.task_id).values(status="awaiting_approval"))
            await notify(
                db=db,
                type="requires_decision",
                priority="critical",
                title="Task requires approval",
                body=question,
                task_id=ctx.task_id,
                project_id=ctx.project_id or None,
            )
            await db.commit()

        await ws_manager.broadcast(
            {
                "event": "task_status_changed",
                "task_id": ctx.task_id,
                "new_status": "awaiting_approval",
                "project_id": ctx.project_id,
            }
        )
        await _do_comment(ctx.task_id, ctx.agent_id, f"Requesting approval:\n\n{question}")
        return ToolResult(ok=True, output="Approval requested.")
    except Exception as exc:
        return ToolResult(ok=False, output="", error=str(exc))
