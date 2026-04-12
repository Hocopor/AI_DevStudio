"""
Skills-система.
Агент может создать Skill, Директор — распространить на других.
"""
import uuid
from typing import Optional
from loguru import logger
from sqlalchemy import select
from core.database import AsyncSessionLocal
from models import AgentSkill


async def get_agent_skills(agent_id: str) -> list[AgentSkill]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AgentSkill)
            .where(AgentSkill.agent_id == agent_id, AgentSkill.is_active == True)
            .order_by(AgentSkill.name)
        )
        return result.scalars().all()


async def create_skill(
    agent_id: str,
    name: str,
    description: str,
    content: str,
    created_by: str,
) -> str:
    """Создать новый Skill для агента"""
    async with AsyncSessionLocal() as db:
        skill = AgentSkill(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            name=name,
            description=description,
            content=content,
            version=1,
            is_active=True,
            created_by=created_by,
        )
        db.add(skill)
        await db.commit()
        logger.info(f"Skill создан: '{name}' для {agent_id} (автор: {created_by})")
        return skill.id


async def update_skill(skill_id: str, content: str, description: Optional[str] = None) -> bool:
    """Обновить Skill — увеличить версию"""
    async with AsyncSessionLocal() as db:
        skill = await db.get(AgentSkill, skill_id)
        if not skill:
            return False
        skill.content = content
        skill.version += 1
        if description:
            skill.description = description
        await db.commit()
        logger.info(f"Skill обновлён: '{skill.name}' v{skill.version}")
        return True


async def distribute_skill(
    skill_id: str,
    target_agent_ids: list[str],
    distributed_by: str,
) -> int:
    """
    Директор распространяет Skill на других агентов.
    Возвращает кол-во созданных копий.
    """
    async with AsyncSessionLocal() as db:
        source = await db.get(AgentSkill, skill_id)
        if not source:
            return 0

        count = 0
        for agent_id in target_agent_ids:
            # Проверить: нет ли уже такого скилла у агента
            existing = await db.execute(
                select(AgentSkill).where(
                    AgentSkill.agent_id == agent_id,
                    AgentSkill.name == source.name,
                    AgentSkill.is_active == True,
                )
            )
            if existing.scalar_one_or_none():
                continue

            copy = AgentSkill(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                name=source.name,
                description=source.description,
                content=source.content,
                version=source.version,
                is_active=True,
                created_by=distributed_by,
            )
            db.add(copy)
            count += 1

        await db.commit()
        logger.info(f"Skill '{source.name}' распространён на {count} агентов")
        return count


async def format_skills_for_prompt(agent_id: str) -> str:
    """Сформировать блок Skills для системного промпта агента"""
    skills = await get_agent_skills(agent_id)
    if not skills:
        return ""

    lines = ["## Твои Skills (специальные инструменты):"]
    for s in skills:
        lines.append(f"\n### {s.name}")
        if s.description:
            lines.append(f"_{s.description}_")
        lines.append(s.content)

    return "\n".join(lines)


async def auto_detect_and_create_skill(
    agent_id: str,
    task_description: str,
    solution: str,
    llm_provider: str,
    llm_model: str,
) -> Optional[str]:
    """
    Агент сам определяет: стоит ли оформить решение в Skill?
    Используется LLM для анализа.
    """
    from services.llm_provider import call_llm

    prompt = (
        f"Ты анализируешь, стоит ли сохранить решение как многоразовый Skill.\n\n"
        f"Задача: {task_description[:300]}\n"
        f"Решение: {solution[:500]}\n\n"
        f"Ответь ТОЛЬКО в JSON (без markdown):\n"
        f'{{"should_create": true/false, "name": "...", "description": "...", "content": "..."}}\n'
        f'should_create=true если решение универсальное и может повториться.'
    )
    try:
        raw = await call_llm(
            provider=llm_provider,
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            agent_id=agent_id,
        )
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data = __import__("json").loads(raw)
        if data.get("should_create") and data.get("name") and data.get("content"):
            skill_id = await create_skill(
                agent_id=agent_id,
                name=data["name"],
                description=data.get("description", ""),
                content=data["content"],
                created_by=agent_id,
            )
            logger.info(f"[{agent_id}] Авто-создан Skill: {data['name']}")
            return skill_id
    except Exception as e:
        logger.debug(f"[{agent_id}] Не удалось авто-создать Skill: {e}")
    return None
