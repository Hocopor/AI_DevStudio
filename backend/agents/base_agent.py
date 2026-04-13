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
from models import Task, TaskComment, Agent, Project, AgentTaskMemory
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
    context_window_tokens: int = 128000
    context_budget_ratio: float = 0.55
    recent_comments_limit: int = 6
    old_comments_for_memory: int = 14

    def _truncate_text(self, text: Optional[str], max_chars: int) -> str:
        if not text:
            return ""
        text = text.strip()
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 12].rstrip() + "\n...[truncated]"

    def _stringify_json_field(self, value, max_chars: int) -> str:
        if not value:
            return "не указано"
        raw = json.dumps(value, ensure_ascii=False)
        return self._truncate_text(raw, max_chars)

    def _make_project_summary(self, project: Optional[Project]) -> str:
        if not project:
            return "Проект не привязан."

        lines = [
            f"Название: {project.title}",
            f"Описание: {self._truncate_text(project.description or 'не указано', 800)}",
            f"Цель: {self._truncate_text(project.goal or 'не указана', 500)}",
            f"Целевая аудитория: {self._truncate_text(project.target_audience or 'не указана', 400)}",
            f"Монетизация: {self._truncate_text(project.monetization_model or 'не указана', 300)}",
            f"Режим автономности: {project.autonomy_mode}",
            f"Метрики успеха: {self._stringify_json_field(project.success_metrics, 700)}",
            f"Roadmap: {self._stringify_json_field(project.roadmap, 900)}",
        ]
        return "\n".join(lines)

    def _compress_comments(self, comments: list[TaskComment]) -> tuple[list[str], list[str], Optional[str], Optional[str]]:
        if not comments:
            return [], [], None, None

        recent = comments[-self.recent_comments_limit :]
        older = comments[:-self.recent_comments_limit]

        recent_lines = [
            f"- [{comment.created_at.isoformat()}] {comment.author}: {self._truncate_text(comment.content, 500)}"
            for comment in recent
        ]
        older_lines = [
            f"- {comment.author}: {self._truncate_text(comment.content, 220)}"
            for comment in older[-self.old_comments_for_memory :]
        ]

        last_owner_reply = next((comment.content for comment in reversed(comments) if comment.author == "owner"), None)
        last_agent_question = next(
            (comment.content for comment in reversed(comments) if comment.author == self.agent_id),
            None,
        )

        return recent_lines, older_lines, last_owner_reply, last_agent_question

    async def _update_memory(
        self,
        task: Task,
        *,
        summary: str,
        key_points: list[str],
        last_owner_reply: Optional[str],
        last_agent_question: Optional[str],
        raw_context_chars: int,
        compressed_context_chars: int,
    ) -> None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AgentTaskMemory).where(
                    AgentTaskMemory.task_id == task.id,
                    AgentTaskMemory.agent_id == self.agent_id,
                )
            )
            memory = result.scalar_one_or_none()
            if not memory:
                memory = AgentTaskMemory(
                    agent_id=self.agent_id,
                    task_id=task.id,
                    project_id=task.project_id,
                )
                db.add(memory)

            memory.summary = summary
            memory.key_points = key_points
            memory.last_owner_reply = last_owner_reply
            memory.last_agent_question = last_agent_question
            memory.raw_context_chars = raw_context_chars
            memory.compressed_context_chars = compressed_context_chars
            await db.commit()

    async def clear_task_memory(self, task_id: str) -> None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AgentTaskMemory).where(
                    AgentTaskMemory.task_id == task_id,
                    AgentTaskMemory.agent_id == self.agent_id,
                )
            )
            memory = result.scalar_one_or_none()
            if memory:
                await db.delete(memory)
                await db.commit()

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

    async def build_task_context(self, task: Task, max_output_tokens: int = 4096) -> str:
        async with AsyncSessionLocal() as db:
            project = await db.get(Project, task.project_id) if task.project_id else None
            result = await db.execute(
                select(TaskComment)
                .where(TaskComment.task_id == task.id)
                .order_by(TaskComment.created_at.asc())
            )
            comments = result.scalars().all()
            result = await db.execute(
                select(AgentTaskMemory).where(
                    AgentTaskMemory.task_id == task.id,
                    AgentTaskMemory.agent_id == self.agent_id,
                )
            )
            memory = result.scalar_one_or_none()

        base_budget_tokens = int(self.context_window_tokens * self.context_budget_ratio) - max_output_tokens
        base_budget_chars = max(3000, base_budget_tokens * 4)
        project_summary = self._make_project_summary(project)
        recent_comment_lines, older_comment_lines, last_owner_reply, last_agent_question = self._compress_comments(comments)

        memory_summary = memory.summary if memory and memory.summary else ""
        memory_key_points = memory.key_points if memory and memory.key_points else []
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
            self._truncate_text(task.description or "не указано", 2000),
        ])

        if project_summary:
            lines.extend([
                "",
                "Контекст проекта:",
                project_summary,
            ])

        if memory_summary or memory_key_points:
            lines.extend(["", "Память агента по этой задаче:"])
            if memory_summary:
                lines.append(self._truncate_text(memory_summary, 2000))
            if memory_key_points:
                lines.extend(f"- {self._truncate_text(point, 300)}" for point in memory_key_points[:12])

        lines.extend(["", "Свежие комментарии по задаче:"])
        if recent_comment_lines:
            lines.extend(recent_comment_lines)
        else:
            lines.append("- комментариев нет")

        lines.extend([
            "",
            "Правила работы с контекстом:",
            "- Учитывай ответы владельца в комментариях как актуальные уточнения.",
            "- Не задавай повторно вопрос, если ответ уже есть в комментариях или в данных проекта.",
            "- Если задача возвращена из awaiting_approval в todo, сначала обработай новые комментарии владельца.",
        ])

        raw_context = "\n".join(lines)
        raw_context_chars = len(raw_context)
        compressed_context = raw_context

        if len(compressed_context) > base_budget_chars:
            memory_lines = []
            if older_comment_lines:
                memory_lines.append("История более ранних комментариев:")
                memory_lines.extend(older_comment_lines)
            if project:
                memory_lines.append("Сжатый проектный контекст:")
                memory_lines.append(project_summary)
            if task.description:
                memory_lines.append("Ключевая задача:")
                memory_lines.append(self._truncate_text(task.description, 1200))

            key_points = []
            if last_owner_reply:
                key_points.append(f"Последний ответ владельца: {self._truncate_text(last_owner_reply, 500)}")
            if last_agent_question:
                key_points.append(f"Последний вопрос агента: {self._truncate_text(last_agent_question, 500)}")
            if task.tags:
                key_points.append(f"Теги: {', '.join(task.tags)}")
            if project and project.goal:
                key_points.append(f"Цель проекта: {self._truncate_text(project.goal, 300)}")

            summary = "\n".join(memory_lines) if memory_lines else "История пока компактная, отдельное сжатие не требуется."
            await self._update_memory(
                task,
                summary=summary,
                key_points=key_points,
                last_owner_reply=last_owner_reply,
                last_agent_question=last_agent_question,
                raw_context_chars=raw_context_chars,
                compressed_context_chars=min(base_budget_chars, len(raw_context)),
            )

            compressed_sections = [
                "Контекст задачи:",
                f"- ID: {task.id}",
                f"- Статус: {task.status}",
                f"- Приоритет: {task.priority}",
                f"- Назначена: {task.assigned_to or 'не назначена'}",
                "",
                "Описание задачи:",
                self._truncate_text(task.description or "не указано", 1200),
                "",
                "Память агента по задаче:",
                self._truncate_text(summary, 2200),
            ]
            if key_points:
                compressed_sections.extend(["", "Ключевые моменты:"])
                compressed_sections.extend(f"- {self._truncate_text(point, 260)}" for point in key_points)
            compressed_sections.extend(["", "Свежие комментарии по задаче:"])
            compressed_sections.extend(recent_comment_lines or ["- комментариев нет"])
            compressed_sections.extend([
                "",
                "Правила работы с контекстом:",
                "- Используй память как источник подтвержденных фактов по задаче.",
                "- Если ответ владельца уже есть, не задавай тот же вопрос повторно.",
            ])
            compressed_context = "\n".join(compressed_sections)
        else:
            await self._update_memory(
                task,
                summary=memory_summary or "Контекст помещается в окно без сильного сжатия.",
                key_points=memory_key_points,
                last_owner_reply=last_owner_reply,
                last_agent_question=last_agent_question,
                raw_context_chars=raw_context_chars,
                compressed_context_chars=len(compressed_context),
            )

        return self._truncate_text(compressed_context, base_budget_chars)

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
        await self.clear_task_memory(task.id)
        await self.comment(task.id, "✅ Готово. Передаю на проверку.")
        logger.info(f"[{self.agent_id}] Завершил: {task.title}")

    async def create_live_plan(self, task: Task) -> dict:
        system = await self.get_full_system_prompt()
        context = await self.build_task_context(task, max_output_tokens=1024)
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
