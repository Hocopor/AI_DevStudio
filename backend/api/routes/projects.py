from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from core.database import get_db
from core.auth import get_current_user
from models import Project, Task
from schemas import ProjectCreate, ProjectUpdate, ProjectOut
from services.ws_manager import ws_manager
import uuid

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    status_filter: str = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    q = select(Project).order_by(Project.created_at.desc())
    if status_filter:
        q = q.where(Project.status == status_filter)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    project = Project(
        id=str(uuid.uuid4()),
        **body.model_dump()
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    await ws_manager.broadcast({"event": "project_created", "project_id": project.id})
    return project


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return project


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    await ws_manager.broadcast({"event": "project_updated", "project_id": project_id})
    return project


@router.delete("/{project_id}", status_code=204)
async def archive_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    project.status = "archived"
    await db.commit()


@router.post("/{project_id}/start", response_model=ProjectOut)
async def start_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    project.status = "active"
    await db.commit()
    await db.refresh(project)
    return project


@router.post("/{project_id}/pause", response_model=ProjectOut)
async def pause_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    project.status = "paused"
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{project_id}/stats")
async def project_stats(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Статистика задач проекта для прогресс-бара"""
    total = await db.scalar(select(func.count()).where(Task.project_id == project_id))
    done = await db.scalar(
        select(func.count()).where(Task.project_id == project_id, Task.status == "done")
    )
    in_progress = await db.scalar(
        select(func.count()).where(Task.project_id == project_id, Task.status == "in_progress")
    )
    return {
        "total": total or 0,
        "done": done or 0,
        "in_progress": in_progress or 0,
        "progress_pct": round((done / total * 100) if total else 0, 1),
    }
