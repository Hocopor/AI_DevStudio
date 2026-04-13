from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from core.auth import get_current_user
from models import Task, TaskComment
from schemas import TaskCreate, TaskUpdate, TaskOut, TaskCommentCreate, TaskCommentOut
from services.ws_manager import ws_manager
from services.notification_service import notify
import uuid

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    project_id: str = Query(None),
    assigned_to: str = Query(None),
    status: str = Query(None),
    priority: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    q = select(Task).order_by(Task.created_at.desc())
    if project_id:
        q = q.where(Task.project_id == project_id)
    if assigned_to:
        q = q.where(Task.assigned_to == assigned_to)
    if status:
        q = q.where(Task.status == status)
    if priority:
        q = q.where(Task.priority == priority)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    payload = body.model_dump()
    if payload.get("assigned_to") and not payload.get("status"):
        payload["status"] = "todo"
    task = Task(id=str(uuid.uuid4()), **payload)
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Уведомить агента через WS
    await ws_manager.broadcast({
        "event": "task_created",
        "task_id": task.id,
        "assigned_to": task.assigned_to,
        "project_id": task.project_id,
    })
    return task


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task


@router.put("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: str,
    body: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    old_status = task.status
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    await db.commit()
    await db.refresh(task)

    # WS событие при смене статуса
    if body.status and body.status != old_status:
        await ws_manager.broadcast({
            "event": "task_status_changed",
            "task_id": task_id,
            "old_status": old_status,
            "new_status": task.status,
            "project_id": task.project_id,
        })

        # Если задача перешла в awaiting_approval — создать уведомление
        if task.status == "awaiting_approval":
            await notify(
                db=db,
                type="requires_decision",
                priority="critical",
                title=f"Требует вашего решения: {task.title}",
                body="Задача ожидает вашего одобрения для продолжения.",
                task_id=task_id,
                project_id=task.project_id,
            )

    return task


# ── КОММЕНТАРИИ ──────────────────────────────

@router.get("/{task_id}/comments", response_model=list[TaskCommentOut])
async def get_comments(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    result = await db.execute(
        select(TaskComment)
        .where(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at.asc())
    )
    return result.scalars().all()


@router.post("/{task_id}/comments", response_model=TaskCommentOut, status_code=201)
async def add_comment(
    task_id: str,
    body: TaskCommentCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    comment = TaskComment(
        id=str(uuid.uuid4()),
        task_id=task_id,
        **body.model_dump(),
    )
    db.add(comment)
    old_status = task.status
    owner_replied_to_approval = body.author == "owner" and task.status == "awaiting_approval"
    if owner_replied_to_approval:
        task.status = "todo"

    await db.commit()
    await db.refresh(comment)
    await db.refresh(task)

    await ws_manager.broadcast({
        "event": "task_comment_added",
        "task_id": task_id,
        "author": comment.author,
        "project_id": task.project_id,
    })

    if owner_replied_to_approval:
        await ws_manager.broadcast({
            "event": "task_status_changed",
            "task_id": task_id,
            "old_status": old_status,
            "new_status": task.status,
            "project_id": task.project_id,
        })

    return comment
