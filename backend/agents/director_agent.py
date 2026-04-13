import json
from models import Task
from base_agent import BaseAgent
from loguru import logger


DIRECTOR_SYSTEM_PROMPT = """Ты — Директор AI DevStudio, главный оркестратор команды AI-агентов.

ТВОЯ РОЛЬ:
- Принимать задачи от владельца студии
- Анализировать задачи, уточнять всё непонятное
- Декомпозировать задачи на подзадачи для специалистов
- Координировать работу команды
- Контролировать качество результатов
- Эскалировать владельцу ТОЛЬКО то, что реально требует его решения

КОМАНДА (Фаза 1):
- backend_dev: Backend-разработчик — серверная логика, API, БД, интеграции

ПРИНЦИПЫ РАБОТЫ:
1. Сначала полностью понять задачу. Если что-то неясно — спроси в комментарии.
2. Составить план декомпозиции: кто что делает, в каком порядке.
3. Создать подзадачи с чёткими описаниями для каждого специалиста.
4. Следить за прогрессом: если задача зависла — уточни у исполнителя.
5. Проверять результаты перед тем как отчитаться владельцу.
6. Маркетинговое мышление: любое решение оцениваешь и с точки зрения влияния на продукт.

ФОРМАТ ОТВЕТОВ:
- Чёткий, деловой стиль
- Без воды и лишних слов
- Конкретные шаги и формулировки
- Всегда объясняй своё решение в комментарии к задаче

ТЫ НЕ:
- Выполняешь техническую работу сам (только координируешь)
- Беспокоишь владельца по мелочам
- Принимаешь финансовые решения без согласования
"""


class DirectorAgent(BaseAgent):
    agent_id = "director"
    name = "Директор"
    role = "CEO / Оркестратор"
    provider = "deepseek"
    model = "deepseek-reasoner"

    available_tools = [
        "create_subtask",
        "comment_task",
        "update_task_status",
        "update_live_plan",
        "request_approval",
        "web_search",
    ]

    @property
    def system_prompt(self) -> str:
        return DIRECTOR_SYSTEM_PROMPT

    async def execute(self, task: Task) -> None:
        """
        Логика директора:
        1. Проанализировать задачу
        2. Определить: нужно ли уточнить у владельца?
        3. Декомпозировать на подзадачи
        4. Назначить исполнителей
        5. Мониторить (через следующие циклы Celery)
        """
        logger.info(f"[director] Обрабатываю задачу: {task.title}")

        # Анализ задачи с LLM
        analysis = await self._analyze_task(task)

        if analysis.get("needs_clarification"):
            # Задать уточняющий вопрос владельцу
            question = analysis["clarification_question"]
            await self.comment(task.id, f"❓ Прежде чем приступить, мне нужно уточнить:\n\n{question}")
            await self.escalate_to_owner(task, question)
            return

        # Декомпозировать на подзадачи
        subtasks = analysis.get("subtasks", [])
        if not subtasks:
            await self.comment(task.id, "⚠️ Не удалось определить подзадачи. Уточняю у владельца.")
            await self.escalate_to_owner(task, "Не могу декомпозировать задачу — слишком мало контекста. Опиши подробнее.")
            return

        # Создать подзадачи
        created = []
        for st in subtasks:
            task_id = await self.create_subtask(
                parent_task=task,
                title=st["title"],
                description=st["description"],
                assigned_to=st["assigned_to"],
                priority=st.get("priority", "medium"),
            )
            created.append(f"- [{st['assigned_to']}] {st['title']}")

        # Отчёт о декомпозиции
        summary = analysis.get("summary", "Задача декомпозирована.")
        await self.comment(
            task.id,
            f"✅ Задача принята в работу.\n\n"
            f"**Анализ:** {summary}\n\n"
            f"**Подзадачи созданы:**\n" + "\n".join(created)
        )

        # Директор остаётся в статусе in_progress (мониторит подзадачи)
        # Завершение — когда все подзадачи будут done
        logger.info(f"[director] Создано {len(created)} подзадач для: {task.title}")

    async def _analyze_task(self, task: Task) -> dict:
        """Анализ задачи — нужны ли уточнения, как декомпозировать"""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"Проанализируй задачу и верни JSON:\n\n"
                    f"Задача: {task.title}\n"
                    f"Описание: {task.description or 'не указано'}\n\n"
                    f"Доступные исполнители: backend_dev\n\n"
                    f"Верни ТОЛЬКО JSON (без markdown):\n"
                    f"{{\n"
                    f'  "needs_clarification": false,\n'
                    f'  "clarification_question": "",\n'
                    f'  "summary": "краткий анализ задачи",\n'
                    f'  "subtasks": [\n'
                    f'    {{\n'
                    f'      "title": "название подзадачи",\n'
                    f'      "description": "подробное описание",\n'
                    f'      "assigned_to": "backend_dev",\n'
                    f'      "priority": "high"\n'
                    f'    }}\n'
                    f'  ]\n'
                    f"}}"
                ),
            },
        ]

        raw = await self._call_llm(messages, task_id=task.id, max_tokens=2048)
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error(f"[director] Ошибка парсинга JSON анализа: {raw[:200]}")
            return {"needs_clarification": True, "clarification_question": "Не смог разобрать задачу. Опишите подробнее."}

    async def check_subtasks_completion(self, parent_task_id: str) -> bool:
        """Проверить, все ли подзадачи завершены"""
        from core.database import AsyncSessionLocal
        from sqlalchemy import select
        from models import Task

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Task).where(Task.parent_task_id == parent_task_id)
            )
            subtasks = result.scalars().all()

        if not subtasks:
            return False

        all_done = all(t.status == "done" for t in subtasks)
        return all_done
