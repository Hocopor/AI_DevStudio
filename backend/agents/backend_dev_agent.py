import json
import httpx
from models import Task
from base_agent import BaseAgent
from services.minio_service import save_agent_artifact
from loguru import logger


BACKEND_DEV_SYSTEM_PROMPT = """Ты — Backend-разработчик AI DevStudio. Опытный Python-разработчик.

ТВОЯ РОЛЬ:
- Проектировать архитектуру серверной части приложений
- Писать API (FastAPI, Flask, Django)
- Проектировать и создавать схемы БД
- Реализовывать бизнес-логику
- Интегрировать внешние API и сервисы
- Писать чистый, документированный, тестируемый код

ТЕХНОЛОГИЧЕСКИЙ СТЕК:
- Python (FastAPI, SQLAlchemy, Pydantic, asyncio)
- PostgreSQL, Redis
- Docker, docker-compose
- REST API, WebSocket
- Аутентификация (JWT, OAuth)

ПРИНЦИПЫ РАБОТЫ:
1. Перед кодингом — чётко понять требования. Неясности уточнить у директора.
2. Составить архитектурный план ДО написания кода.
3. Писать код поэтапно, обновляя живой план после каждого шага.
4. Код должен быть читаемым, с комментариями на русском.
5. Каждый файл — сохранить в хранилище (MinIO).
6. После завершения — отчёт директору с описанием что сделано и как запустить.

ОТЧЁТ О ВЫПОЛНЕНИИ (обязательно включает):
- Что реализовано
- Структура файлов
- Как запустить / применить
- Что требует внимания (если есть)

ТЫ НЕ:
- Деплоишь в production без подтверждения DevOps
- Принимаешь архитектурные решения, влияющие на весь проект, без согласования с директором
"""


class BackendDevAgent(BaseAgent):
    agent_id = "backend_dev"
    name = "Backend Dev"
    role = "Backend-разработчик"
    provider = "deepseek"
    model = "deepseek-chat"

    available_tools = [
        "comment_task",
        "update_task_status",
        "update_live_plan",
        "web_search",
        "write_file",
        "execute_code",
    ]

    @property
    def base_system_prompt(self) -> str:
        return BACKEND_DEV_SYSTEM_PROMPT

    async def execute(self, task: Task) -> None:
        logger.info(f"[backend_dev] Выполняю: {task.title}")

        # Генерация кода / архитектуры через LLM
        result = await self._implement(task)

        # Сохранить артефакты в MinIO
        if result.get("files"):
            for filename, content in result["files"].items():
                if task.project_id:
                    save_agent_artifact(
                        project_id=task.project_id,
                        agent_id=self.agent_id,
                        filename=filename,
                        data=content.encode("utf-8"),
                        content_type="text/plain",
                    )

        # Обновить живой план — все шаги done
        plan = task.live_plan or {"steps": [], "notes": ""}
        for step in plan.get("steps", []):
            step["status"] = "done"
        plan["notes"] = result.get("summary", "")
        await self.update_live_plan(task.id, plan)

        # Отчёт директору
        report = self._format_report(result)
        await self.comment(task.id, report)

        # Завершить задачу
        await self.mark_done(task)

    async def _implement(self, task: Task) -> dict:
        """Реализовать задачу через LLM"""
        messages = [
            {"role": "system", "content": await self.get_full_system_prompt()},
            {
                "role": "user",
                "content": (
                    f"Выполни задачу разработки.\n\n"
                    f"Задача: {task.title}\n"
                    f"Описание: {task.description or 'не указано'}\n\n"
                    f"Верни результат в JSON (без markdown):\n"
                    f"{{\n"
                    f'  "summary": "что реализовано",\n'
                    f'  "architecture": "описание архитектуры",\n'
                    f'  "files": {{"filename.py": "содержимое файла"}},\n'
                    f'  "how_to_run": "как запустить",\n'
                    f'  "notes": "что требует внимания"\n'
                    f"}}"
                ),
            },
        ]

        raw = await self._call_llm(messages, task_id=task.id, max_tokens=4096)
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Если не JSON — вернуть как текстовый результат
            return {
                "summary": "Результат получен",
                "files": {"result.md": raw},
                "notes": "",
            }

    def _format_report(self, result: dict) -> str:
        lines = ["✅ **Задача выполнена**\n"]
        if result.get("summary"):
            lines.append(f"**Реализовано:** {result['summary']}\n")
        if result.get("architecture"):
            lines.append(f"**Архитектура:** {result['architecture']}\n")
        if result.get("files"):
            lines.append(f"**Файлы:** {', '.join(result['files'].keys())}")
        if result.get("how_to_run"):
            lines.append(f"**Запуск:** {result['how_to_run']}\n")
        if result.get("notes"):
            lines.append(f"**Внимание:** {result['notes']}")
        return "\n".join(lines)
