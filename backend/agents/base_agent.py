"""
Обновлённый базовый класс агента (Фаза 2).
Unified LLM provider + Skills + авто-создание Skills.
"""
import json
import uuid
from abc import ABC, abstractmethod
from typing import Optional
from loguru import logger
from sqlalchemy import select, update

from core.database import AsyncSessionLocal
from models import Task, TaskComment, Agent, Project
from services.llm_provider import call_llm
from services.notification_service import notify
from services.skills_service import format_skills_for_prompt, auto_detect_and_create_skill


class BaseAgent(ABC):
    agent_id: str = ""
    name: str = ""
    role: str = ""
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    available_tools: list[str] = []

    async def _get_current_provider(self) -> tuple[str, str]:
        async with AsyncSessionLocal() as db:
            agent = await db.get(Agent, self.agent_id)
            if agent and agent.provider and agent.model:
                return agent.provider, agent.model
        return self.provider, self.model

    async def _call_llm(self, messages: list[dict], task_id: Optional[str] = None, max_tokens: int = 4096) -> str:
        provider, model = await self._get_current_provider()
        return await call_llm(
            provider=provider, model=model, messages=messages,
            max_tokens=max_tokens, agent_id=self.agent_id, task_id=task_id,
        )

    @property
    @abstractmethod
    def base_system_prompt(self) -> str:
        pass

    async def get_full_system_prompt(self) -> str:
        base = self.base_system_prompt
        async with AsyncSessionLocal() as db:
            agent = await db.get(Agent, self.agent_id)
            if agent and agent.system_prompt:
                base = agent.system_prompt
        skills_block = await format_skills_for_prompt(self.agent_id)
        return (base + "\n\n" + skills_block) if skills_block else base

    async def get_pending_tasks(self) -> list[Task]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Task)
                .where(
                    Task.assigned_to == self.agent_id,
                    Task.status.in_(("todo", "backlog")),
                )
                .order_by(Task.priority.desc(), Task.created_at.asc())
            )
            return result.scalars().all()

    async def build_task_context(self, task: Task) -> str:
        async with AsyncSessionLocal() as db:
            project = await db.get(Project, task.project_id) if task.project_id else None
            result = await db.execute(
                select(TaskComment)
                .where(TaskComment.task_id == task.id)
                .order_by(TaskComment.created_at.asc())
            )
            comments = result.scalars().all()

        lines = [
            "Контекст задачи:",
            f"- ID: {task.id}",
            f"- Статус: {task.status}",
            f"- Приоритет: {task.priority}",
            f"- Назначена: {task.assigned_to or 'не назначена'}",
            f"- Теги: {', '.join(task.tags) if task.tags else 'нет'}",
        ]

        if task.live_plan:
            lines.append(f"- Live plan notes: {task.live_plan.get('notes', '') or 'нет'}")

        lines.extend([
            "",
            "Описание задачи:",
            task.description or "не указано",
        ])

        if project:
            lines.extend([
                "",
                "Контекст проекта:",
                f"- Название: {project.title}",
                f"- Описание: {project.description or 'не указано'}",
                f"- Цель: {project.goal or 'не указана'}",
                f"- Целевая аудитория: {project.target_audience or 'не указана'}",
                f"- Модель монетизации: {project.monetization_model or 'не указана'}",
                f"- Режим автономности: {project.autonomy_mode}",
                f"- Метрики успеха: {json.dumps(project.success_metrics, ensure_ascii=False) if project.success_metrics else 'не указаны'}",
                f"- Roadmap: {json.dumps(project.roadmap, ensure_ascii=False) if project.roadmap else 'не указан'}",
            ])

        lines.extend(["", "Комментарии по задаче:"])
        if comments:
            for comment in comments[-20:]:
                lines.append(f"- [{comment.created_at.isoformat()}] {comment.author}: {comment.content}")
        else:
            lines.append("- комментариев нет")

        lines.extend([
            "",
            "Правила работы с контекстом:",
            "- Учитывай ответы владельца в комментариях как актуальные уточнения.",
            "- Не задавай повторно вопрос, если ответ уже есть в комментариях или в данных проекта.",
            "- Если задача возвращена из awaiting_approval в todo, сначала обработай новые комментарии владельца.",
        ])

        return "\n".join(lines)

    async def take_task(self, task: Task):
        async with AsyncSessionLocal() as db:
            await db.execute(update(Task).where(Task.id == task.id).values(status="in_progress"))
            await db.execute(
                update(Agent).where(Agent.id == self.agent_id)
                .values(status="active", current_task_id=task.id)
            )
            await db.commit()
        logger.info(f"[{self.agent_id}] Взял: {task.title}")

    async def update_live_plan(self, task_id: str, plan: dict):
        async with AsyncSessionLocal() as db:
            await db.execute(update(Task).where(Task.id == task_id).values(live_plan=plan))
            await db.commit()
        from services.ws_manager import ws_manager
        await ws_manager.broadcast({"event": "task_plan_updated", "task_id": task_id})

    async def comment(self, task_id: str, content: str, attachments: list = None):
        async with AsyncSessionLocal() as db:
            c = TaskComment(
                id=str(uuid.uuid4()), task_id=task_id,
                author=self.agent_id, content=content, attachments=attachments or [],
            )
            db.add(c)
            task = await db.get(Task, task_id)
            project_id = task.project_id if task else None
            await db.commit()
        from services.ws_manager import ws_manager
        await ws_manager.broadcast(
            {"event": "task_comment_added", "task_id": task_id, "author": self.agent_id},
            project_id=project_id,
        )

    async def create_subtask(self, parent_task: Task, title: str, description: str,
                              assigned_to: str, priority: str = "medium") -> str:
        async with AsyncSessionLocal() as db:
            t = Task(
                id=str(uuid.uuid4()), project_id=parent_task.project_id,
                parent_task_id=parent_task.id, title=title, description=description,
                status="todo", priority=priority, created_by=self.agent_id, assigned_to=assigned_to,
            )
            db.add(t)
            await db.commit()
        logger.info(f"[{self.agent_id}] → [{assigned_to}]: {title}")
        return t.id

    async def escalate_to_owner(self, task: Task, question: str):
        async with AsyncSessionLocal() as db:
            await notify(db=db, type="requires_decision", priority="critical",
                title=f"Требует решения: {task.title}", body=question,
                task_id=task.id, project_id=task.project_id)
        await self._set_status(task.id, "awaiting_approval")
        await self.comment(task.id, f"⚠️ Эскалирую владельцу:\n\n{question}")

    async def _set_status(self, task_id: str, status: str):
        async with AsyncSessionLocal() as db:
            await db.execute(update(Task).where(Task.id == task_id).values(status=status))
            await db.commit()
        from services.ws_manager import ws_manager
        await ws_manager.broadcast({"event": "task_status_changed", "task_id": task_id, "new_status": status})

    async def mark_done(self, task: Task):
        await self._set_status(task.id, "review")
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Agent).where(Agent.id == self.agent_id)
                .values(status="idle", current_task_id=None, tasks_completed=Agent.tasks_completed + 1)
            )
            await db.commit()
        await self.comment(task.id, "✅ Готово. Передаю на проверку.")
        logger.info(f"[{self.agent_id}] Завершил: {task.title}")

    async def create_live_plan(self, task: Task) -> dict:
        system = await self.get_full_system_prompt()
        context = await self.build_task_context(task)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": (
                f"Составь живой план. ТОЛЬКО JSON без markdown:\n"
                f'{{"steps":[{{"step":"...","status":"pending"}}],"notes":"..."}}\n\n'
                f"Задача: {task.title}\n\n{context}"
            )},
        ]
        raw = await self._call_llm(messages, task_id=task.id, max_tokens=1024)
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        try:
            plan = json.loads(raw)
        except Exception:
            plan = {"steps": [{"step": "Выполнить задачу", "status": "pending"}], "notes": ""}
        await self.update_live_plan(task.id, plan)
        steps_text = "\n".join(
            f"{'✅' if s['status']=='done' else '⏳'} {s['step']}"
            for s in plan.get("steps", [])
        )
        await self.comment(task.id, f"📋 **Живой план:**\n\n{steps_text}")
        return plan

    async def try_create_skill(self, task: Task, result_summary: str):
        provider, model = await self._get_current_provider()
        await auto_detect_and_create_skill(
            agent_id=self.agent_id,
            task_description=task.title + "\n" + (task.description or ""),
            solution=result_summary,
            llm_provider=provider,
            llm_model=model,
        )

    @abstractmethod
    async def execute(self, task: Task) -> None:
        pass

    async def run(self):
        tasks = await self.get_pending_tasks()
        if not tasks:
            logger.debug(f"[{self.agent_id}] Нет задач")
            return
        for task in tasks:
            try:
                await self.take_task(task)
                await self.create_live_plan(task)
                await self.execute(task)
            except Exception as e:
                logger.error(f"[{self.agent_id}] Ошибка {task.id}: {e}")
                await self.comment(task.id, f"❌ Ошибка: {str(e)}")
                async with AsyncSessionLocal() as db:
                    await notify(db=db, type="system_error", priority="high",
                        title=f"Ошибка {self.name}: {task.title}", body=str(e), task_id=task.id)
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        update(Agent).where(Agent.id == self.agent_id)
                        .values(status="idle", current_task_id=None)
                    )
                    await db.commit()
