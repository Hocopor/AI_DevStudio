"""
Task and project context tools.
"""
from __future__ import annotations

import json
import uuid

from loguru import logger

from agents.context import get_pcd, save_pcd
from agents.tools.registry import ToolParam, ToolResult, tool


async def _publish_task_event(event: dict):
    try:
        from core.redis import get_redis

        redis = await get_redis()
        await redis.publish("task_events", json.dumps(event, ensure_ascii=False))
    except Exception as exc:
        logger.debug(f"Redis publish error: {exc}")


@tool(
    name="create_subtask",
    description="Create a subtask and assign it to a specialist agent.",
    params=[
        ToolParam("title", "string", "Clear subtask title.", required=True),
        ToolParam("description", "string", "Detailed description for the assignee.", required=True),
        ToolParam(
            "assigned_to",
            "string",
            "Specialist agent id.",
            required=True,
            enum=[
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
            ],
        ),
        ToolParam("priority", "string", "Priority.", required=False, enum=["low", "medium", "high", "critical"]),
    ],
    agents=["director"],
)
async def create_subtask(title: str, description: str, assigned_to: str, ctx, priority: str = "medium") -> ToolResult:
    try:
        from core.database import AsyncSessionLocal
        from models import Task
        from services.ws_manager import ws_manager
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            existing = await db.scalar(
                select(Task).where(
                    Task.parent_task_id == ctx.task_id,
                    Task.assigned_to == assigned_to,
                    Task.title == title,
                    Task.status.in_(("backlog", "todo", "in_progress", "review", "awaiting_approval")),
                )
            )
            if existing:
                return ToolResult(
                    ok=True,
                    output=f"Matching subtask already exists: {existing.id[:8]} for {assigned_to}: {title}",
                    data={"task_id": existing.id, "deduplicated": True},
                )

            task = Task(
                id=str(uuid.uuid4()),
                project_id=ctx.project_id or None,
                parent_task_id=ctx.task_id,
                title=title,
                description=description,
                status="todo",
                priority=priority,
                created_by=ctx.agent_id,
                assigned_to=assigned_to,
            )
            db.add(task)
            await db.commit()
            task_id = task.id

        await ws_manager.broadcast(
            {
                "event": "task_created",
                "task_id": task_id,
                "assigned_to": assigned_to,
                "project_id": ctx.project_id,
            }
        )
        await _publish_task_event(
            {
                "event": "task_assigned",
                "task_id": task_id,
                "assigned_to": assigned_to,
                "project_id": ctx.project_id,
            }
        )
        return ToolResult(
            ok=True,
            output=f"Created subtask {task_id[:8]} for {assigned_to}: {title}",
            data={"task_id": task_id},
        )
    except Exception as exc:
        return ToolResult(ok=False, output="", error=str(exc))


@tool(name="get_subtasks", description="List subtasks of the current task.", params=[])
async def get_subtasks(ctx) -> ToolResult:
    try:
        from core.database import AsyncSessionLocal
        from models import Task
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Task).where(Task.parent_task_id == ctx.task_id).order_by(Task.created_at)
            )
            tasks = result.scalars().all()

        if not tasks:
            return ToolResult(ok=True, output="No subtasks yet.", data=[])

        lines = []
        data = []
        for task in tasks:
            lines.append(f"- [{task.status}] {task.assigned_to}: {task.title}")
            data.append(
                {
                    "id": task.id,
                    "title": task.title,
                    "status": task.status,
                    "assigned_to": task.assigned_to,
                }
            )
        return ToolResult(ok=True, output="\n".join(lines), data=data)
    except Exception as exc:
        return ToolResult(ok=False, output="", error=str(exc))


@tool(
    name="get_task_details",
    description="Get current task details including live plan and status.",
    params=[ToolParam("task_id", "string", "Task id. Defaults to current task.", required=False)],
)
async def get_task_details(ctx, task_id: str = "") -> ToolResult:
    try:
        from core.database import AsyncSessionLocal
        from models import Task

        target_task_id = task_id or ctx.task_id
        async with AsyncSessionLocal() as db:
            task = await db.get(Task, target_task_id)

        if not task:
            return ToolResult(ok=False, output="", error="Task not found.")

        payload = {
            "id": task.id,
            "title": task.title,
            "description": task.description or "",
            "status": task.status,
            "priority": task.priority,
            "assigned_to": task.assigned_to,
            "parent_task_id": task.parent_task_id,
            "live_plan": task.live_plan,
            "tags": task.tags,
        }
        return ToolResult(ok=True, output=json.dumps(payload, ensure_ascii=False, indent=2), data=payload)
    except Exception as exc:
        return ToolResult(ok=False, output="", error=str(exc))


@tool(name="wait_for_subtasks", description="Check whether subtasks are done and summarize pending work.", params=[])
async def wait_for_subtasks(ctx) -> ToolResult:
    result = await get_subtasks(ctx=ctx)
    if not result.ok:
        return result

    tasks = result.data or []
    if not tasks:
        return ToolResult(ok=True, output="No subtasks exist.")

    pending = [task for task in tasks if task["status"] not in {"done", "review"}]
    if pending:
        return ToolResult(
            ok=True,
            output=(
                f"Still waiting for {len(pending)} subtasks:\n"
                + "\n".join(f"- [{task['status']}] {task['assigned_to']}: {task['title']}" for task in pending)
            ),
            data={"pending": pending, "all_done": False},
        )

    return ToolResult(ok=True, output="All subtasks are completed or in review.", data={"pending": [], "all_done": True})


@tool(name="get_project_context", description="Read the shared Project Context Document.", params=[])
async def get_project_context(ctx) -> ToolResult:
    pcd = await get_pcd(ctx.project_id or "")
    return ToolResult(ok=True, output=pcd.to_prompt_text(for_agent=ctx.agent_id), data=pcd.to_dict())


@tool(
    name="update_project_context",
    description="Update shared project memory with a new decision, event, artifact, or tech stack item.",
    params=[
        ToolParam("decision", "string", "Key project decision.", required=False),
        ToolParam("event", "string", "Project timeline event.", required=False),
        ToolParam("artifact_path", "string", "Artifact path to record.", required=False),
        ToolParam("tech_stack_item", "string", "Tech stack item to add.", required=False),
    ],
)
async def update_project_context(
    ctx,
    decision: str = "",
    event: str = "",
    artifact_path: str = "",
    tech_stack_item: str = "",
) -> ToolResult:
    pcd = await get_pcd(ctx.project_id or "")

    if decision:
        pcd.add_decision(decision)
    if event:
        pcd.add_event(event)
    if artifact_path:
        pcd.set_artifact(ctx.agent_id, artifact_path)
    if tech_stack_item and tech_stack_item not in pcd.tech_stack:
        pcd.tech_stack.append(tech_stack_item)

    await save_pcd(pcd)
    return ToolResult(ok=True, output="Project context updated.", data=pcd.to_dict())


@tool(
    name="update_live_plan",
    description="Replace the current task live plan with a new ordered list of steps.",
    params=[
        ToolParam("steps_json", "string", "JSON array of {step, status} objects.", required=True),
        ToolParam("notes", "string", "Optional live plan notes.", required=False),
    ],
)
async def update_live_plan(ctx, steps_json: str, notes: str = "") -> ToolResult:
    try:
        from core.database import AsyncSessionLocal
        from models import Task
        from sqlalchemy import update

        steps = json.loads(steps_json)
        if not isinstance(steps, list):
            return ToolResult(ok=False, output="", error="steps_json must be a JSON array.")

        plan = {"steps": steps, "notes": notes}
        async with AsyncSessionLocal() as db:
            await db.execute(update(Task).where(Task.id == ctx.task_id).values(live_plan=plan))
            await db.commit()

        ctx.live_plan = plan
        return ToolResult(ok=True, output="Live plan updated.", data=plan)
    except Exception as exc:
        return ToolResult(ok=False, output="", error=str(exc))
