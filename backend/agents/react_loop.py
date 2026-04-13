"""
ReAct loop engine for tool-driven agent execution.
"""
from __future__ import annotations

import traceback
from typing import Optional

from loguru import logger

from agents.context import AgentContext
from agents.tools.registry import ToolResult, execute_tool, get_tools_for_agent, validate_tool_call
from core.config import settings


class ReActEngine:
    MAX_RETRIES_ON_INVALID_TOOL = 3

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.max_steps = settings.agent_max_steps

    async def run(self, ctx: AgentContext) -> str:
        logger.info(
            f"[{self.agent_id}] ReAct loop start | task={ctx.task_id[:8]} | max_steps={self.max_steps or 'inf'}"
        )

        step = 0
        invalid_retries = 0

        while True:
            if self.max_steps > 0 and step >= self.max_steps:
                logger.warning(f"[{self.agent_id}] Step limit reached: {self.max_steps}")
                return await self._handle_step_limit(ctx, step)

            llm_response = await self._think(ctx)
            if llm_response is None:
                return "LLM did not return a valid response."

            if llm_response.get("type") == "text":
                return llm_response.get("content", "")

            if llm_response.get("type") != "tool_call":
                return f"Unexpected LLM response format: {llm_response}"

            tool_name = llm_response["tool_name"]
            tool_args = llm_response.get("tool_args", {})
            thought = llm_response.get("thought", "")

            if tool_name == "mark_task_done":
                return tool_args.get("result", "Task completed.")

            validated = validate_tool_call(tool_name, tool_args, self.agent_id)
            if not validated.ok:
                invalid_retries += 1
                ctx.add_step(
                    step_num=step,
                    thought=thought,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    tool_result=f"Validation error: {validated.error}",
                    ok=False,
                )
                if invalid_retries >= self.MAX_RETRIES_ON_INVALID_TOOL:
                    return (
                        f"Agent could not select a valid tool after {invalid_retries} attempts: "
                        f"{validated.error}"
                    )
                continue

            invalid_retries = 0
            tool_result = await execute_tool(tool_name, validated.args, ctx)
            ctx.add_step(
                step_num=step,
                thought=thought,
                tool_name=tool_name,
                tool_args=validated.args,
                tool_result=tool_result.output if tool_result.ok else tool_result.error,
                ok=tool_result.ok,
            )
            await self._update_plan_step(ctx, step, tool_result)
            step += 1

    async def _think(self, ctx: AgentContext) -> Optional[dict]:
        from services.llm_provider import call_llm_with_tools

        try:
            return await call_llm_with_tools(
                agent_id=self.agent_id,
                task_id=ctx.task_id,
                messages=ctx.build_messages(),
                tools=get_tools_for_agent(self.agent_id),
                max_tokens=2048,
            )
        except Exception as exc:
            logger.error(f"[{self.agent_id}] _think error: {exc}\n{traceback.format_exc()}")
            return None

    async def _update_plan_step(self, ctx: AgentContext, step_num: int, result: ToolResult):
        try:
            from core.database import AsyncSessionLocal
            from models import Task
            from sqlalchemy import update

            plan = ctx.live_plan or {"steps": [], "notes": ""}
            steps = plan.get("steps", [])

            updated = False
            for index, step in enumerate(steps):
                if step.get("status") in {"pending", "in_progress"}:
                    steps[index]["status"] = "done" if result.ok else "pending"
                    updated = True
                    break

            if not updated:
                steps.append(
                    {
                        "step": f"{ctx.steps[-1].tool_name}({ctx.steps[-1].tool_args})",
                        "status": "done" if result.ok else "pending",
                    }
                )

            plan["steps"] = steps
            plan["notes"] = result.output if result.ok else result.error
            ctx.live_plan = plan

            async with AsyncSessionLocal() as db:
                await db.execute(update(Task).where(Task.id == ctx.task_id).values(live_plan=plan))
                await db.commit()
        except Exception as exc:
            logger.warning(f"[{self.agent_id}] Failed to update live plan after step {step_num}: {exc}")

    async def _handle_step_limit(self, ctx: AgentContext, step: int) -> str:
        try:
            from agents.tools.communication import _do_comment
            from core.database import AsyncSessionLocal
            from models import Task
            from sqlalchemy import update

            summary = ctx.get_progress_summary()
            plan = ctx.live_plan or {"steps": [], "notes": ""}
            plan["notes"] = summary["summary"]

            async with AsyncSessionLocal() as db:
                await db.execute(update(Task).where(Task.id == ctx.task_id).values(live_plan=plan, status="in_progress"))
                await db.commit()

            await _do_comment(
                ctx.task_id,
                ctx.agent_id,
                f"Reached step limit ({step}). Saved progress and will continue in the next cycle.",
            )
            return summary["summary"]
        except Exception as exc:
            logger.warning(f"[{self.agent_id}] Failed to persist step limit progress: {exc}")
            return "Step limit reached."
