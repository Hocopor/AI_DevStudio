import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
from sqlalchemy import select, update

from core.database import AsyncSessionLocal
from models import Task, TaskComment, Agent, APIUsageLog, Notification
from services.notification_service import notify


class BaseAgent(ABC):
    """
    Базовый класс для всех AI-агентов.

    Жизненный цикл задачи:
    1. take_task()       — взять задачу, сменить статус → in_progress
    2. create_live_plan() — составить живой план (обязательно!)
    3. execute()         — выполнять шаги плана с инструментами
    4. report_done()     — отчитаться директору, сменить статус → review/done
    """

    agent_id: str = ""
    name: str = ""
    role: str = ""
    provider: str = "deepseek"
    model: str = "deepseek-chat"

    # Инструменты, доступные агенту (переопределяется в подклассах)
    available_tools: list[str] = [
        "web_search",
        "create_task",
        "comment_task",
        "update_task_status",
        "update_live_plan",
        "request_approval",
    ]

    def __init__(self):
        self._llm = None

    # ── LLM ──────────────────────────────────────────

    def _get_llm_client(self):
        if self._llm:
            return self._llm
        if self.provider == "deepseek":
            from openai import AsyncOpenAI
            from core.config import settings
            self._llm = AsyncOpenAI(
                api_key=settings.deepseek_api_key,
                base_url="https://api.deepseek.com",
            )
        elif self.provider == "google":
            import google.generativeai as genai
            from core.config import settings
            genai.configure(api_key=settings.google_ai_studio_key)
            self._llm = genai.GenerativeModel(self.model)
        return self._llm

    async def _call_llm(
        self,
        messages: list[dict],
        task_id: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> str:
        """Вызов LLM с логированием использования токенов"""
        client = self._get_llm_client()

        if self.provider == "deepseek":
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
            )
            content = response.choices[0].message.content
            usage = response.usage
            await self._log_usage(
                task_id=task_id,
                tokens_in=usage.prompt_tokens,
                tokens_out=usage.completion_tokens,
            )
            return content

        elif self.provider == "google":
            prompt = "\n".join(m["content"] for m in messages)
            response = await client.generate_content_async(prompt)
            return response.text

        return ""

    async def _log_usage(self, task_id: Optional[str], tokens_in: int, tokens_out: int):
        """Логировать использование API"""
        # Примерная стоимость DeepSeek (обновить по актуальным ценам)
        cost = (tokens_in * 0.00000014) + (tokens_out * 0.00000028)
        async with AsyncSessionLocal() as db:
            log = APIUsageLog(
                id=str(uuid.uuid4()),
                agent_id=self.agent_id,
                provider=self.provider,
                model=self.model,
                tokens_input=tokens_in,
                tokens_output=tokens_out,
                cost_usd=cost,
                task_id=task_id,
            )
            db.add(log)
            await db.commit()

    # ── СИСТЕМНЫЙ ПРОМПТ ─────────────────────────────

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Системный промпт агента — переопределяется в подклассе"""
        pass

    # ── РАБОТА С ЗАДАЧАМИ ─────────────────────────────

    async def get_pending_tasks(self) -> list[Task]:
        """Получить задачи со статусом todo, назначенные на этого агента"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Task)
                .where(Task.assigned_to == self.agent_id, Task.status == "todo")
                .order_by(Task.priority.desc(), Task.created_at.asc())
            )
            return result.scalars().all()

    async def take_task(self, task: Task):
        """Взять задачу в работу"""
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Task)
                .where(Task.id == task.id)
                .values(status="in_progress")
            )
            await db.execute(
                update(Agent)
                .where(Agent.id == self.agent_id)
                .values(status="active", current_task_id=task.id)
            )
            await db.commit()
        logger.info(f"[{self.agent_id}] Взял задачу: {task.title}")

    async def update_status(self, task_id: str, status: str):
        """Сменить статус задачи"""
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Task).where(Task.id == task_id).values(status=status)
            )
            await db.commit()

    async def update_live_plan(self, task_id: str, plan: dict):
        """Обновить живой план задачи"""
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Task).where(Task.id == task_id).values(live_plan=plan)
            )
            await db.commit()

    async def comment(self, task_id: str, content: str, attachments: list = None):
        """Добавить комментарий к задаче"""
        async with AsyncSessionLocal() as db:
            c = TaskComment(
                id=str(uuid.uuid4()),
                task_id=task_id,
                author=self.agent_id,
                content=content,
                attachments=attachments or [],
            )
            db.add(c)
            await db.commit()

    async def create_subtask(
        self,
        parent_task: Task,
        title: str,
        description: str,
        assigned_to: str,
        priority: str = "medium",
    ) -> str:
        """Создать подзадачу и назначить другому агенту"""
        async with AsyncSessionLocal() as db:
            t = Task(
                id=str(uuid.uuid4()),
                project_id=parent_task.project_id,
                parent_task_id=parent_task.id,
                title=title,
                description=description,
                status="todo",
                priority=priority,
                created_by=self.agent_id,
                assigned_to=assigned_to,
            )
            db.add(t)
            await db.commit()
        logger.info(f"[{self.agent_id}] Создал подзадачу для {assigned_to}: {title}")
        return t.id

    async def escalate_to_owner(self, task: Task, question: str):
        """Эскалировать вопрос владельцу (только через директора!)"""
        async with AsyncSessionLocal() as db:
            await notify(
                db=db,
                type="requires_decision",
                priority="critical",
                title=f"Требует вашего решения: {task.title}",
                body=question,
                task_id=task.id,
                project_id=task.project_id,
            )
            await self.update_status(task.id, "awaiting_approval")
        await self.comment(task.id, f"⚠️ Эскалирую владельцу:\n\n{question}")

    async def mark_done(self, task: Task):
        """Завершить задачу"""
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Task).where(Task.id == task.id).values(status="done")
            )
            await db.execute(
                update(Agent)
                .where(Agent.id == self.agent_id)
                .values(
                    status="idle",
                    current_task_id=None,
                    tasks_completed=Agent.tasks_completed + 1,
                )
            )
            await db.commit()
        await self.comment(task.id, "✅ Задача выполнена. Жду проверки директора.")
        logger.info(f"[{self.agent_id}] Завершил задачу: {task.title}")

    # ── ЖИВОЙ ПЛАН ────────────────────────────────────

    async def create_live_plan(self, task: Task) -> dict:
        """Составить живой план с помощью LLM и сохранить"""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"Составь живой план выполнения задачи.\n\n"
                    f"Задача: {task.title}\n"
                    f"Описание: {task.description or 'не указано'}\n\n"
                    f"Ответь ТОЛЬКО в формате JSON:\n"
                    f'{{"steps": [{{"step": "...", "status": "pending"}}], "notes": "..."}}'
                ),
            },
        ]

        raw = await self._call_llm(messages, task_id=task.id, max_tokens=1024)

        # Очистить от markdown-обёртки если есть
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()

        try:
            plan = json.loads(raw)
        except json.JSONDecodeError:
            plan = {
                "steps": [{"step": "Выполнить задачу", "status": "pending"}],
                "notes": raw[:500],
            }

        await self.update_live_plan(task.id, plan)
        await self.comment(task.id, f"📋 Составил живой план:\n\n" + "\n".join(
            f"{'✅' if s['status'] == 'done' else '⏳'} {s['step']}"
            for s in plan.get("steps", [])
        ))
        logger.info(f"[{self.agent_id}] Живой план создан для: {task.title}")
        return plan

    # ── ГЛАВНЫЙ МЕТОД ─────────────────────────────────

    @abstractmethod
    async def execute(self, task: Task) -> None:
        """
        Основная логика выполнения задачи.
        Переопределяется в каждом агенте.
        """
        pass

    async def run(self):
        """
        Цикл агента: берёт задачи по очереди и выполняет.
        Вызывается из Celery.
        """
        tasks = await self.get_pending_tasks()
        if not tasks:
            logger.debug(f"[{self.agent_id}] Нет задач в очереди")
            return

        for task in tasks:
            try:
                await self.take_task(task)
                await self.create_live_plan(task)
                await self.execute(task)
            except Exception as e:
                logger.error(f"[{self.agent_id}] Ошибка при выполнении задачи {task.id}: {e}")
                await self.comment(task.id, f"❌ Ошибка выполнения: {str(e)}")
                async with AsyncSessionLocal() as db:
                    await notify(
                        db=db,
                        type="system_error",
                        priority="high",
                        title=f"Ошибка агента {self.name}",
                        body=str(e),
                        task_id=task.id,
                    )
