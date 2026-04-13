"""
Agent execution context for the ReAct loop and shared project memory.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from loguru import logger


class ProjectContextDocument:
    REDIS_KEY = "pcd:{project_id}"
    MAX_DECISIONS = 20
    MAX_TIMELINE = 50

    def __init__(self, data: dict):
        self.project_id: str = data.get("project_id", "")
        self.goal: str = data.get("goal", "")
        self.target_audience: str = data.get("target_audience", "")
        self.monetization: str = data.get("monetization", "")
        self.key_decisions: list[str] = data.get("key_decisions", [])
        self.artifacts: dict[str, str] = data.get("artifacts", {})
        self.active_agents: dict[str, str] = data.get("active_agents", {})
        self.timeline: list[dict] = data.get("timeline", [])
        self.tech_stack: list[str] = data.get("tech_stack", [])

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "goal": self.goal,
            "target_audience": self.target_audience,
            "monetization": self.monetization,
            "key_decisions": self.key_decisions,
            "artifacts": self.artifacts,
            "active_agents": self.active_agents,
            "timeline": self.timeline,
            "tech_stack": self.tech_stack,
        }

    def to_prompt_text(self, for_agent: str = "") -> str:
        lines = ["## Project Context Document"]
        if self.goal:
            lines.append(f"Goal: {self.goal}")
        if self.target_audience:
            lines.append(f"Target Audience: {self.target_audience}")
        if self.monetization:
            lines.append(f"Monetization: {self.monetization}")
        if self.tech_stack:
            lines.append(f"Tech Stack: {', '.join(self.tech_stack)}")

        if self.key_decisions:
            lines.extend(["", "Key Decisions:"])
            lines.extend(f"- {decision}" for decision in self.key_decisions[-10:])

        visible_artifacts = {
            agent_id: path
            for agent_id, path in self.artifacts.items()
            if agent_id != for_agent
        }
        if visible_artifacts:
            lines.extend(["", "Team Artifacts:"])
            lines.extend(f"- {agent_id}: {path}" for agent_id, path in visible_artifacts.items())

        if self.timeline:
            lines.extend(["", "Recent Events:"])
            lines.extend(f"- {event.get('date', '')}: {event.get('event', '')}" for event in self.timeline[-5:])

        return "\n".join(line for line in lines if line)

    def add_decision(self, decision: str):
        self.key_decisions.append(decision)
        if len(self.key_decisions) > self.MAX_DECISIONS:
            self.key_decisions = self.key_decisions[-self.MAX_DECISIONS :]

    def add_event(self, event: str):
        self.timeline.append(
            {
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                "event": event,
            }
        )
        if len(self.timeline) > self.MAX_TIMELINE:
            self.timeline = self.timeline[-self.MAX_TIMELINE :]

    def set_artifact(self, agent_id: str, file_path: str):
        self.artifacts[agent_id] = file_path

    def set_active(self, agent_id: str, task_id: str):
        self.active_agents[agent_id] = task_id

    def set_idle(self, agent_id: str):
        self.active_agents.pop(agent_id, None)


async def get_pcd(project_id: str) -> ProjectContextDocument:
    if not project_id:
        return ProjectContextDocument({})

    try:
        from core.redis import get_redis

        redis = await get_redis()
        key = ProjectContextDocument.REDIS_KEY.format(project_id=project_id)
        raw = await redis.get(key)
        if raw:
            return ProjectContextDocument(json.loads(raw))

        from core.database import AsyncSessionLocal
        from models import Project

        async with AsyncSessionLocal() as db:
            project = await db.get(Project, project_id)
            if project:
                pcd = ProjectContextDocument(
                    {
                        "project_id": project_id,
                        "goal": project.goal or "",
                        "target_audience": project.target_audience or "",
                        "monetization": project.monetization_model or "",
                        "key_decisions": [],
                        "artifacts": {},
                        "active_agents": {},
                        "timeline": [],
                    }
                )
                await save_pcd(pcd)
                return pcd
    except Exception as exc:
        logger.warning(f"PCD load error: {exc}")

    return ProjectContextDocument({"project_id": project_id})


async def save_pcd(pcd: ProjectContextDocument):
    if not pcd.project_id:
        return

    try:
        from core.redis import get_redis

        redis = await get_redis()
        key = ProjectContextDocument.REDIS_KEY.format(project_id=pcd.project_id)
        await redis.setex(key, 86400 * 7, json.dumps(pcd.to_dict(), ensure_ascii=False))
    except Exception as exc:
        logger.warning(f"PCD save error: {exc}")


@dataclass
class ReActStep:
    step_num: int
    thought: str
    tool_name: str
    tool_args: dict
    tool_result: str
    ok: bool


@dataclass
class AgentContext:
    agent_id: str
    agent_name: str
    task_id: str
    project_id: str
    system_prompt: str
    task_title: str
    task_description: str
    live_plan: dict
    task_comments: list[dict]
    pcd: ProjectContextDocument
    task_context_summary: str = ""
    steps: list[ReActStep] = field(default_factory=list)
    final_result: str = ""

    MAX_COMMENTS_FULL = 10

    def add_step(self, step_num: int, thought: str, tool_name: str, tool_args: dict, tool_result: str, ok: bool):
        self.steps.append(
            ReActStep(
                step_num=step_num,
                thought=thought,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=tool_result,
                ok=ok,
            )
        )

    def build_messages(self) -> list[dict]:
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.append({"role": "user", "content": self._build_task_block()})

        for step in self.steps:
            messages.append(
                {
                    "role": "assistant",
                    "content": step.thought or "",
                    "tool_calls": [
                        {
                            "id": f"call_{step.step_num}",
                            "type": "function",
                            "function": {
                                "name": step.tool_name,
                                "arguments": json.dumps(step.tool_args, ensure_ascii=False),
                            },
                        }
                    ],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": f"call_{step.step_num}",
                    "content": ("OK: " if step.ok else "ERROR: ") + step.tool_result,
                }
            )

        return messages

    def _build_task_block(self) -> str:
        parts = [f"# Current Task\n{self.task_title}"]
        if self.task_description:
            parts.append(f"\nDescription:\n{self.task_description}")
        if self.task_context_summary:
            parts.append(f"\nCondensed Task Context:\n{self.task_context_summary}")

        steps = (self.live_plan or {}).get("steps", [])
        if steps:
            parts.append("\nLive Plan:")
            for index, step in enumerate(steps, start=1):
                parts.append(f"{index}. [{step.get('status', 'pending')}] {step.get('step', '')}")

        if self.task_comments:
            parts.append("\nTask Comments:")
            comments = self.task_comments
            if len(comments) > self.MAX_COMMENTS_FULL:
                parts.append(f"- Earlier comments omitted: {len(comments) - self.MAX_COMMENTS_FULL}")
                comments = comments[-self.MAX_COMMENTS_FULL :]
            for comment in comments:
                content = comment.get("content", "")
                if len(content) > 700:
                    content = content[:700].rstrip() + "... [truncated]"
                parts.append(f"- [{comment.get('author', '?')}] {content}")

        pcd_text = self.pcd.to_prompt_text(for_agent=self.agent_id)
        if pcd_text:
            parts.append("\n" + pcd_text)

        parts.append(
            "\nUse tools to work step by step. Do not ask repeated questions if the answer is already "
            "present in comments, project context, or the condensed task context. When the task is "
            "fully complete, call `mark_task_done` with a concise but sufficient final result."
        )
        return "\n".join(parts)

    def get_progress_summary(self) -> dict:
        done_steps = [step for step in self.steps if step.ok]
        return {
            "steps_done": len(done_steps),
            "last_tool": self.steps[-1].tool_name if self.steps else "",
            "last_result": self.steps[-1].tool_result[:200] if self.steps else "",
            "summary": f"Completed {len(done_steps)} ReAct steps. Continue from the last successful tool result.",
        }


async def build_context(agent_id: str, agent_name: str, task, system_prompt: str, task_context_summary: str = "") -> AgentContext:
    from core.database import AsyncSessionLocal
    from models import TaskComment
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TaskComment).where(TaskComment.task_id == task.id).order_by(TaskComment.created_at.asc())
        )
        comments = [
            {"author": comment.author, "content": comment.content, "ts": comment.created_at.isoformat()}
            for comment in result.scalars().all()
        ]

    pcd = await get_pcd(task.project_id or "")

    return AgentContext(
        agent_id=agent_id,
        agent_name=agent_name,
        task_id=task.id,
        project_id=task.project_id or "",
        system_prompt=system_prompt,
        task_title=task.title,
        task_description=task.description or "",
        live_plan=task.live_plan or {"steps": [], "notes": ""},
        task_comments=comments,
        pcd=pcd,
        task_context_summary=task_context_summary,
    )
