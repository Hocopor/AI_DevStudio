from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timezone, timedelta
from core.database import get_db
from core.auth import get_current_user
from models import Task, Agent, Notification, Project, APIUsageLog

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # Задачи, требующие решения владельца
    requires_decision_q = await db.execute(
        select(Notification)
        .where(Notification.type == "requires_decision", Notification.is_read == False)
        .order_by(Notification.created_at.desc())
        .limit(10)
    )
    requires_decision = requires_decision_q.scalars().all()

    # Блокеры — задачи in_progress, не обновлявшиеся более 1 часа
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    blockers_q = await db.execute(
        select(Task)
        .where(
            Task.status == "in_progress",
            Task.updated_at < one_hour_ago,
        )
        .order_by(Task.updated_at.asc())
        .limit(5)
    )
    blockers = blockers_q.scalars().all()

    # Статус агентов
    agents_q = await db.execute(select(Agent).order_by(Agent.id))
    agents = agents_q.scalars().all()

    # Активные проекты с прогрессом
    active_projects_q = await db.execute(
        select(Project)
        .where(Project.status == "active")
        .order_by(Project.updated_at.desc())
        .limit(5)
    )
    active_projects = active_projects_q.scalars().all()

    project_progress = []
    for proj in active_projects:
        total = await db.scalar(select(func.count()).where(Task.project_id == proj.id))
        done = await db.scalar(
            select(func.count()).where(Task.project_id == proj.id, Task.status == "done")
        )
        in_prog = await db.scalar(
            select(func.count()).where(Task.project_id == proj.id, Task.status == "in_progress")
        )
        project_progress.append({
            "id": proj.id,
            "title": proj.title,
            "status": proj.status,
            "total_tasks": total or 0,
            "done_tasks": done or 0,
            "in_progress_tasks": in_prog or 0,
            "progress_pct": round((done / total * 100) if total else 0, 1),
        })

    # Метрики сегодня
    tasks_today_done = await db.scalar(
        select(func.count()).where(
            Task.status == "done",
            Task.updated_at >= today_start,
        )
    )
    tasks_in_progress = await db.scalar(
        select(func.count()).where(Task.status == "in_progress")
    )

    # Расход на AI сегодня
    ai_cost_today = await db.scalar(
        select(func.sum(APIUsageLog.cost_usd)).where(
            APIUsageLog.created_at >= today_start
        )
    )

    return {
        "requires_decision": [
            {
                "id": n.id,
                "type": n.type,
                "priority": n.priority,
                "title": n.title,
                "body": n.body,
                "task_id": n.task_id,
                "project_id": n.project_id,
                "created_at": n.created_at.isoformat(),
            }
            for n in requires_decision
        ],
        "blockers": [
            {
                "id": t.id,
                "title": t.title,
                "assigned_to": t.assigned_to,
                "project_id": t.project_id,
                "updated_at": t.updated_at.isoformat(),
                "hours_stuck": round((datetime.now(timezone.utc) - t.updated_at).total_seconds() / 3600, 1),
            }
            for t in blockers
        ],
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "role": a.role,
                "status": a.status,
                "provider": a.provider,
                "model": a.model,
                "current_task_id": a.current_task_id,
                "tasks_completed": a.tasks_completed,
            }
            for a in agents
        ],
        "active_projects": project_progress,
        "today_metrics": {
            "tasks_done_today": tasks_today_done or 0,
            "tasks_in_progress": tasks_in_progress or 0,
            "ai_cost_usd_today": float(ai_cost_today or 0),
        },
    }
