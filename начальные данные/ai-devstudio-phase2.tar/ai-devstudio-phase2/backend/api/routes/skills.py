from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import Optional
from core.database import get_db
from core.auth import get_current_user
from models import AgentSkill
from services.skills_service import create_skill, update_skill, distribute_skill
import uuid

router = APIRouter(prefix="/skills", tags=["skills"])


class SkillCreate(BaseModel):
    agent_id: str
    name: str
    description: Optional[str] = ""
    content: str


class SkillUpdate(BaseModel):
    content: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class SkillDistribute(BaseModel):
    target_agent_ids: list[str]


@router.get("")
async def list_skills(
    agent_id: str = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    q = select(AgentSkill).order_by(AgentSkill.agent_id, AgentSkill.name)
    if agent_id:
        q = q.where(AgentSkill.agent_id == agent_id)
    result = await db.execute(q)
    skills = result.scalars().all()
    return [
        {
            "id": s.id, "agent_id": s.agent_id, "name": s.name,
            "description": s.description, "content": s.content,
            "version": s.version, "is_active": s.is_active,
            "created_by": s.created_by, "created_at": s.created_at,
        }
        for s in skills
    ]


@router.post("", status_code=201)
async def create_skill_route(
    body: SkillCreate,
    _: str = Depends(get_current_user),
):
    skill_id = await create_skill(
        agent_id=body.agent_id,
        name=body.name,
        description=body.description or "",
        content=body.content,
        created_by="owner",
    )
    return {"id": skill_id}


@router.put("/{skill_id}")
async def update_skill_route(
    skill_id: str,
    body: SkillUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    skill = await db.get(AgentSkill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill не найден")

    if body.content is not None:
        await update_skill(skill_id, body.content, body.description)
    if body.is_active is not None:
        await db.execute(
            update(AgentSkill).where(AgentSkill.id == skill_id).values(is_active=body.is_active)
        )
        await db.commit()
    return {"detail": "Обновлено"}


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    skill = await db.get(AgentSkill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill не найден")
    await db.delete(skill)
    await db.commit()


@router.post("/{skill_id}/distribute")
async def distribute_skill_route(
    skill_id: str,
    body: SkillDistribute,
    _: str = Depends(get_current_user),
):
    count = await distribute_skill(skill_id, body.target_agent_ids, distributed_by="owner")
    return {"distributed_to": count}
