"""
Base agent with context compression, shared memory, and ReAct execution.
"""
from __future__ import annotations

import json
import traceback
import uuid
from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger
from sqlalchemy import select, update

from agents.context import AgentContext, build_context, get_pcd, save_pcd
from agents.react_loop import ReActEngine, ReActRunResult
import agents.tools  # noqa: F401
from core.database import AsyncSessionLocal
from models import Agent, AgentTaskMemory, Project, Task, TaskComment
from services.llm_provider import call_llm
from services.notification_service import notify
from services.skills_service import auto_detect_and_create_skill, format_skills_for_prompt


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

    @property
    @abstractmethod
    def base_system_prompt(self) -> str:
        pass

    async def execute(self, task: Task) -> None:
        raise NotImplementedError

    def _truncate_text(self, text: Optional[str], max_chars: int) -> str:
        if not text:
            return ""
        text = text.strip()
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 12].rstrip() + "\n...[truncated]"

    def _stringify_json_field(self, value, max_chars: int) -> str:
        if not value:
            return "not specified"
        raw = json.dumps(value, ensure_ascii=False)
        return self._truncate_text(raw, max_chars)

    def _make_project_summary(self, project: Optional[Project]) -> str:
        if not project:
            return "Project is not attached."

        lines = [
            f"Title: {project.title}",
            f"Description: {self._truncate_text(project.description or 'not specified', 800)}",
            f"Goal: {self._truncate_text(project.goal or 'not specified', 500)}",
            f"Target Audience: {self._truncate_text(project.target_audience or 'not specified', 400)}",
            f"Monetization: {self._truncate_text(project.monetization_model or 'not specified', 300)}",
            f"Autonomy Mode: {project.autonomy_mode}",
            f"Success Metrics: {self._stringify_json_field(project.success_metrics, 700)}",
            f"Roadmap: {self._stringify_json_field(project.roadmap, 900)}",
        ]
        return "\n".join(lines)

    def _compress_comments(self, comments: list[TaskComment]) -> tuple[list[str], list[str], Optional[str], Optional[str]]:
        if not comments:
            return [], [], None, None

        recent = comments[-self.recent_comments_limit :]
        older = comments[: -self.recent_comments_limit]

        recent_lines = [
            f"- [{comment.created_at.isoformat()}] {comment.author}: {self._truncate_text(comment.content, 500)}"
            for comment in recent
        ]
        older_lines = [
            f"- {comment.author}: {self._truncate_text(comment.content, 220)}"
            for comment in older[-self.old_comments_for_memory :]
        ]

        last_owner_reply = next((comment.content for comment in reversed(comments) if comment.author == "owner"), None)
        last_agent_question = next((comment.content for comment in reversed(comments) if comment.author == self.agent_id), None)

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
                memory = AgentTaskMemory(agent_id=self.agent_id, task_id=task.id, project_id=task.project_id)
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
            provider=provider,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            agent_id=self.agent_id,
            task_id=task_id,
        )

    def _tool_usage_protocol(self) -> str:
        return (
            "Execution Protocol:\n"
            "- Work iteratively through available tools.\n"
            "- Reuse project context, comments, and condensed task context before asking questions.\n"
            "- If you produce a durable artifact, save it with write_file.\n"
            "- If you need clarification from the owner, use request_approval only for true blockers.\n"
            "- If you need clarification from the director, use ask_director.\n"
            "- When the work is fully complete, call mark_task_done with a concise final result.\n"
            "- Do not output raw JSON plans unless a tool explicitly asks for JSON.\n"
        )

    async def get_full_system_prompt(self) -> str:
        base = self.base_system_prompt
        async with AsyncSessionLocal() as db:
            agent = await db.get(Agent, self.agent_id)
            if agent and agent.system_prompt:
                base = agent.system_prompt
        skills_block = await format_skills_for_prompt(self.agent_id)
        prompt = base + "\n\n" + self._tool_usage_protocol()
        return (prompt + "\n\n" + skills_block) if skills_block else prompt

    async def get_pending_tasks(self) -> list[Task]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Task)
                .where(Task.assigned_to == self.agent_id, Task.status.in_(("backlog", "todo", "in_progress")))
                .order_by(Task.priority.desc(), Task.created_at.asc())
            )
            return result.scalars().all()

    async def build_task_context(self, task: Task, max_output_tokens: int = 4096) -> str:
        async with AsyncSessionLocal() as db:
            project = await db.get(Project, task.project_id) if task.project_id else None
            result = await db.execute(
                select(TaskComment).where(TaskComment.task_id == task.id).order_by(TaskComment.created_at.asc())
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
            "Task Context:",
            f"- ID: {task.id}",
            f"- Status: {task.status}",
            f"- Priority: {task.priority}",
            f"- Assigned To: {task.assigned_to or 'unassigned'}",
            f"- Tags: {', '.join(task.tags) if task.tags else 'none'}",
        ]

        if task.live_plan:
            lines.append(f"- Live plan notes: {task.live_plan.get('notes', '') or 'none'}")

        lines.extend(["", "Task Description:", self._truncate_text(task.description or "not specified", 2000)])
        if project_summary:
            lines.extend(["", "Project Context:", project_summary])

        if memory_summary:
            lines.extend(["", "Existing Agent Memory:", self._truncate_text(memory_summary, 1600)])
        if memory_key_points:
            lines.extend(["", "Memory Key Points:"])
            lines.extend(f"- {self._truncate_text(point, 260)}" for point in memory_key_points)

        lines.extend(["", "Recent Task Comments:"])
        lines.extend(recent_comment_lines or ["- no comments"])
        lines.extend(
            [
                "",
                "Context Rules:",
                "- Treat owner comments as the latest clarifications.",
                "- Do not ask a repeated question if the answer is already in comments or project data.",
                "- If the task came back from awaiting_approval to todo, process the owner reply first.",
            ]
        )

        raw_context = "\n".join(lines)
        raw_context_chars = len(raw_context)
        compressed_context = raw_context

        if len(compressed_context) > base_budget_chars:
            memory_lines = []
            if older_comment_lines:
                memory_lines.append("Earlier comment history:")
                memory_lines.extend(older_comment_lines)
            if project:
                memory_lines.extend(["Project summary:", project_summary])
            if task.description:
                memory_lines.extend(["Core task:", self._truncate_text(task.description, 1200)])

            key_points = []
            if last_owner_reply:
                key_points.append(f"Latest owner reply: {self._truncate_text(last_owner_reply, 500)}")
            if last_agent_question:
                key_points.append(f"Latest agent question: {self._truncate_text(last_agent_question, 500)}")
            if task.tags:
                key_points.append(f"Tags: {', '.join(task.tags)}")
            if project and project.goal:
                key_points.append(f"Project goal: {self._truncate_text(project.goal, 300)}")

            summary = "\n".join(memory_lines) if memory_lines else "Context is compact enough; no heavy summary required."
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
                "Task Context:",
                f"- ID: {task.id}",
                f"- Status: {task.status}",
                f"- Priority: {task.priority}",
                f"- Assigned To: {task.assigned_to or 'unassigned'}",
                "",
                "Task Description:",
                self._truncate_text(task.description or "not specified", 1200),
                "",
                "Agent Memory:",
                self._truncate_text(summary, 2200),
            ]
            if key_points:
                compressed_sections.extend(["", "Key Points:"])
                compressed_sections.extend(f"- {self._truncate_text(point, 260)}" for point in key_points)
            compressed_sections.extend(["", "Recent Task Comments:"])
            compressed_sections.extend(recent_comment_lines or ["- no comments"])
            compressed_sections.extend(
                [
                    "",
                    "Context Rules:",
                    "- Use memory as the source of confirmed facts.",
                    "- If the owner already answered, do not ask the same question again.",
                ]
            )
            compressed_context = "\n".join(compressed_sections)
        else:
            await self._update_memory(
                task,
                summary=memory_summary or "Context fits within the working window without strong compression.",
                key_points=memory_key_points,
                last_owner_reply=last_owner_reply,
                last_agent_question=last_agent_question,
                raw_context_chars=raw_context_chars,
                compressed_context_chars=len(compressed_context),
            )

        return self._truncate_text(compressed_context, base_budget_chars)

    async def _set_agent_active(self, task: Task):
        async with AsyncSessionLocal() as db:
            task_values = {}
            if task.status in {"backlog", "todo"}:
                task_values["status"] = "in_progress"

            await db.execute(update(Task).where(Task.id == task.id).values(**task_values))
            await db.execute(
                update(Agent).where(Agent.id == self.agent_id).values(status="active", current_task_id=task.id)
            )
            await db.commit()

    async def _set_agent_idle(self):
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Agent).where(Agent.id == self.agent_id).values(status="idle", current_task_id=None)
            )
            await db.commit()

    async def update_live_plan(self, task_id: str, plan: dict):
        async with AsyncSessionLocal() as db:
            await db.execute(update(Task).where(Task.id == task_id).values(live_plan=plan))
            await db.commit()
        from services.ws_manager import ws_manager

        await ws_manager.broadcast({"event": "task_plan_updated", "task_id": task_id})

    async def comment(self, task_id: str, content: str, attachments: list = None):
        from agents.tools.communication import _do_comment

        await _do_comment(task_id, self.agent_id, content)

    async def create_subtask(
        self, parent_task: Task, title: str, description: str, assigned_to: str, priority: str = "medium"
    ) -> str:
        async with AsyncSessionLocal() as db:
            task = Task(
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
            db.add(task)
            await db.commit()
            task_id = task.id
        logger.info(f"[{self.agent_id}] -> [{assigned_to}] {title}")
        return task_id

    async def escalate_to_owner(self, task: Task, question: str):
        async with AsyncSessionLocal() as db:
            await notify(
                db=db,
                type="requires_decision",
                priority="critical",
                title=f"Decision required: {task.title}",
                body=question,
                task_id=task.id,
                project_id=task.project_id,
            )
        await self._set_status(task.id, "awaiting_approval")
        await self.comment(task.id, f"Escalating to owner:\n\n{question}")

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
                update(Agent)
                .where(Agent.id == self.agent_id)
                .values(status="idle", current_task_id=None, tasks_completed=Agent.tasks_completed + 1)
            )
            await db.commit()
        await self.clear_task_memory(task.id)
        await self.comment(task.id, "Task completed. Handing over for review.")
        logger.info(f"[{self.agent_id}] Completed: {task.title}")

    async def create_live_plan(self, task: Task) -> dict:
        system = await self.get_full_system_prompt()
        context = await self.build_task_context(task, max_output_tokens=1024)
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    "Create a short live plan. Return JSON only with the shape "
                    '{"steps":[{"step":"...","status":"pending"}],"notes":"..."}'
                    f"\n\nTask: {task.title}\n\n{context}"
                ),
            },
        ]
        raw = await self._call_llm(messages, task_id=task.id, max_tokens=1024)
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        try:
            plan = json.loads(raw)
        except Exception:
            plan = {"steps": [{"step": "Execute the task", "status": "pending"}], "notes": ""}
        await self.update_live_plan(task.id, plan)
        steps_text = "\n".join(
            f"{'done' if step['status'] == 'done' else 'pending'} - {step['step']}" for step in plan.get("steps", [])
        )
        await self.comment(task.id, f"Live plan created:\n\n{steps_text}")
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

    async def _reload_task(self, task_id: str) -> Optional[Task]:
        async with AsyncSessionLocal() as db:
            return await db.get(Task, task_id)

    async def _initialize_task(self, task: Task):
        if not task.live_plan or not task.live_plan.get("steps"):
            await self.create_live_plan(task)

        if task.project_id:
            pcd = await get_pcd(task.project_id)
            pcd.set_active(self.agent_id, task.id)
            await save_pcd(pcd)

    async def _finalize_task(self, task: Task, result: str, ctx: AgentContext):
        from agents.tools.communication import _do_comment

        await _do_comment(task.id, self.agent_id, f"Task completed.\n\n{result}")

        async with AsyncSessionLocal() as db:
            await db.execute(update(Task).where(Task.id == task.id).values(status="review"))
            await db.execute(
                update(Agent)
                .where(Agent.id == self.agent_id)
                .values(status="idle", current_task_id=None, tasks_completed=Agent.tasks_completed + 1)
            )
            await db.commit()

        await self.clear_task_memory(task.id)

        if task.project_id:
            pcd = await get_pcd(task.project_id)
            pcd.set_idle(self.agent_id)
            pcd.add_event(f"{self.name} finished: {task.title[:60]}")
            await save_pcd(pcd)

        if task.parent_task_id:
            from agents.tools.communication import _publish_task_event

            await _publish_task_event(
                {
                    "event": "subtask_completed",
                    "task_id": task.id,
                    "agent_id": self.agent_id,
                    "parent_task_id": task.parent_task_id,
                    "project_id": task.project_id,
                }
            )

        await self.try_create_skill(task, result)
        logger.info(f"[{self.agent_id}] Finalized task {task.id}")

    async def _handle_task_error(self, task: Task, exc: Exception):
        logger.error(f"[{self.agent_id}] Task {task.id} failed: {exc}\n{traceback.format_exc()}")
        await self.comment(task.id, f"Error while processing task:\n\n{exc}")
        async with AsyncSessionLocal() as db:
            await notify(
                db=db,
                type="system_error",
                priority="high",
                title=f"{self.name} failed on task",
                body=str(exc),
                task_id=task.id,
                project_id=task.project_id,
            )

        if task.project_id:
            pcd = await get_pcd(task.project_id)
            pcd.set_idle(self.agent_id)
            pcd.add_event(f"{self.name} hit an error on: {task.title[:60]}")
            await save_pcd(pcd)

        await self._set_agent_idle()

    async def _process_task(self, task: Task):
        logger.info(f"[{self.agent_id}] Processing: {task.title[:80]}")
        try:
            await self._set_agent_active(task)
            if task.status in {"backlog", "todo"}:
                await self._initialize_task(task)

            system_prompt = await self.get_full_system_prompt()
            task_context_summary = await self.build_task_context(task, max_output_tokens=2048)
            ctx = await build_context(
                agent_id=self.agent_id,
                agent_name=self.name,
                task=task,
                system_prompt=system_prompt,
                task_context_summary=task_context_summary,
            )

            engine = ReActEngine(self.agent_id)
            run_result = await engine.run(ctx)
            result = run_result.result

            task_after = await self._reload_task(task.id)
            if task_after and run_result.terminal_reason == "completed" and task_after.status == "in_progress":
                await self._finalize_task(task_after, result, ctx)
            elif task_after and run_result.terminal_reason == "invalid_tool_retries":
                await self._handle_invalid_tool_retries(task_after, result)
            elif task_after and task_after.status == "awaiting_approval":
                if task_after.project_id:
                    pcd = await get_pcd(task_after.project_id)
                    pcd.set_idle(self.agent_id)
                    await save_pcd(pcd)
                await self._set_agent_idle()
            elif task_after and task_after.status == "review":
                await self._set_agent_idle()
        except Exception as exc:
            await self._handle_task_error(task, exc)

    async def _handle_invalid_tool_retries(self, task: Task, result: str):
        summary = (
            f"{self.name} не смог корректно завершить шаг из-за ошибки вызова инструмента.\n\n"
            f"{result}\n\n"
            "Задача возвращена в согласование. Проверьте комментарий агента и при необходимости дайте уточнение."
        )
        await self._set_status(task.id, "awaiting_approval")
        await self.comment(
            task.id,
            "Ошибка tool-calling. Не удалось корректно сформировать вызов инструмента после нескольких попыток.\n\n"
            f"{result}",
        )
        async with AsyncSessionLocal() as db:
            await notify(
                db=db,
                type="system_error",
                priority="high",
                title=f"{self.name} требует внимания по задаче",
                body=summary,
                task_id=task.id,
                project_id=task.project_id,
            )

        if task.project_id:
            pcd = await get_pcd(task.project_id)
            pcd.set_idle(self.agent_id)
            pcd.add_event(f"{self.name} paused on invalid tool call: {task.title[:60]}")
            await save_pcd(pcd)

        await self._set_agent_idle()

    async def run(self):
        tasks = await self.get_pending_tasks()
        if not tasks:
            logger.debug(f"[{self.agent_id}] No tasks")
            return

        for task in tasks:
            await self._process_task(task)
