"""
Tool registry and validation for ReAct agents.
"""
from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

from loguru import logger


@dataclass
class ToolParam:
    name: str
    type: str
    description: str
    required: bool = True
    enum: list = field(default_factory=list)


@dataclass
class ToolDefinition:
    name: str
    description: str
    params: list[ToolParam]
    func: Callable
    agent_ids: list[str]


@dataclass
class ToolResult:
    ok: bool
    output: str
    error: str = ""
    data: Any = None


@dataclass
class ValidatedToolCall:
    ok: bool
    args: dict
    error: str = ""


_registry: dict[str, ToolDefinition] = {}


def tool(name: str, description: str, params: list[ToolParam] | None = None, agents: list[str] | None = None):
    def decorator(func: Callable):
        _registry[name] = ToolDefinition(
            name=name,
            description=description,
            params=params or [],
            func=func,
            agent_ids=agents or [],
        )
        return func

    return decorator


def get_tools_for_agent(agent_id: str) -> list[ToolDefinition]:
    return [
        definition
        for definition in _registry.values()
        if not definition.agent_ids or agent_id in definition.agent_ids
    ]


def to_openai_schema(tools: list[ToolDefinition]) -> list[dict]:
    schemas = []
    for tool_def in tools:
        properties = {}
        required = []
        for param in tool_def.params:
            schema = {"type": param.type, "description": param.description}
            if param.enum:
                schema["enum"] = param.enum
            properties[param.name] = schema
            if param.required:
                required.append(param.name)
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tool_def.name,
                    "description": tool_def.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                        "additionalProperties": False,
                    },
                },
            }
        )
    return schemas


def to_google_schema(tools: list[ToolDefinition]) -> list[dict]:
    function_declarations = []
    for tool_def in tools:
        properties = {}
        required = []
        for param in tool_def.params:
            schema = {"type": param.type.upper(), "description": param.description}
            if param.enum:
                schema["enum"] = param.enum
            properties[param.name] = schema
            if param.required:
                required.append(param.name)
        function_declarations.append(
            {
                "name": tool_def.name,
                "description": tool_def.description,
                "parameters": {
                    "type": "OBJECT",
                    "properties": properties,
                    "required": required,
                },
            }
        )
    return [{"function_declarations": function_declarations}] if function_declarations else []


def validate_tool_call(tool_name: str, tool_args: dict, agent_id: str) -> ValidatedToolCall:
    tool_def = _registry.get(tool_name)
    if not tool_def:
        return ValidatedToolCall(ok=False, args={}, error=f"Unknown tool: {tool_name}")

    if tool_def.agent_ids and agent_id not in tool_def.agent_ids:
        return ValidatedToolCall(ok=False, args={}, error=f"Tool {tool_name} is not allowed for {agent_id}")

    validated = {}
    for param in tool_def.params:
        value = tool_args.get(param.name)
        if value is None:
            if param.required:
                return ValidatedToolCall(ok=False, args={}, error=f"Missing required param: {param.name}")
            continue

        if param.enum and value not in param.enum:
            return ValidatedToolCall(
                ok=False,
                args={},
                error=f"Invalid value for {param.name}: {value}. Allowed: {param.enum}",
            )

        validated[param.name] = value

    return ValidatedToolCall(ok=True, args=validated)


async def execute_tool(tool_name: str, tool_args: dict, ctx) -> ToolResult:
    tool_def = _registry.get(tool_name)
    if not tool_def:
        return ToolResult(ok=False, output="", error=f"Unknown tool: {tool_name}")

    try:
        return await tool_def.func(ctx=ctx, **tool_args)
    except Exception as exc:
        logger.error(f"Tool {tool_name} failed: {exc}\n{traceback.format_exc()}")
        return ToolResult(ok=False, output="", error=str(exc))
