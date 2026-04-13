"""
Provider-agnostic LLM layer with optional tool calling.
Supports DeepSeek, Google AI Studio, and Codex OAuth.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Optional

from loguru import logger

from core.config import settings


class LimitExceeded(Exception):
    pass


class ProviderError(Exception):
    pass


MODEL_COST_TABLE = {
    "deepseek-chat": {"in": 0.00000014, "out": 0.00000028},
    "deepseek-reasoner": {"in": 0.00000055, "out": 0.00000219},
    "gemini-2.0-flash": {"in": 0.000000075, "out": 0.0000003},
    "gemini-1.5-pro": {"in": 0.00000125, "out": 0.000005},
    "gpt-4o": {"in": 0.0000025, "out": 0.00001},
    "gpt-4o-mini": {"in": 0.00000015, "out": 0.0000006},
}


def _estimate_message_tokens(messages: list[dict]) -> int:
    total = 0
    for message in messages:
        total += max(1, len(message.get("content") or "") // 4)
        if message.get("tool_calls"):
            total += max(1, len(json.dumps(message["tool_calls"], ensure_ascii=False)) // 4)
    return total


async def _get_agent_config(agent_id: str) -> tuple[str, str]:
    try:
        from core.database import AsyncSessionLocal
        from models import Agent

        async with AsyncSessionLocal() as db:
            agent = await db.get(Agent, agent_id)
            if agent and agent.provider and agent.model:
                return agent.provider, agent.model
    except Exception:
        pass
    return "deepseek", "deepseek-chat"


async def _get_active_codex_account() -> Optional[dict]:
    from core.database import AsyncSessionLocal
    from models import CodexAccount
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CodexAccount)
            .where(CodexAccount.is_active == True, CodexAccount.is_current == True)
            .limit(1)
        )
        account = result.scalar_one_or_none()
        if account:
            return {"id": account.id, "token": account.oauth_token_encrypted, "label": account.label}
    return None


async def _switch_codex_account(failed_id: str) -> Optional[dict]:
    from core.database import AsyncSessionLocal
    from models import CodexAccount
    from sqlalchemy import select, update
    from services.notification_service import notify

    async with AsyncSessionLocal() as db:
        await db.execute(update(CodexAccount).where(CodexAccount.id == failed_id).values(is_current=False))
        result = await db.execute(
            select(CodexAccount)
            .where(CodexAccount.is_active == True, CodexAccount.is_current == False)
            .order_by(CodexAccount.priority.asc())
            .limit(1)
        )
        next_account = result.scalar_one_or_none()
        if not next_account:
            await db.commit()
            logger.error("Codex: all accounts exhausted.")
            return None

        await db.execute(update(CodexAccount).where(CodexAccount.id == next_account.id).values(is_current=True))
        await notify(
            db=db,
            type="provider_limit",
            priority="high",
            title="Codex account switched",
            body=f"Limit exhausted. Switched to '{next_account.label}'.",
        )
        await db.commit()
        logger.warning(f"Codex: switched to '{next_account.label}'")
        return {"id": next_account.id, "token": next_account.oauth_token_encrypted, "label": next_account.label}


async def _get_codex_token() -> str:
    account = await _get_active_codex_account()
    if not account:
        raise ProviderError("No active Codex accounts.")
    return account["token"]


async def _call_deepseek(messages: list[dict], model: str, max_tokens: int, api_key: str) -> tuple[str, int, int]:
    from openai import AsyncOpenAI, RateLimitError

    client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    try:
        total_tokens_in = 0
        total_tokens_out = 0
        aggregated_content: list[str] = []
        conversation = list(messages)

        for _ in range(6):
            response = await client.chat.completions.create(
                model=model,
                messages=conversation,
                max_tokens=max_tokens,
                temperature=0.7,
            )
            content = response.choices[0].message.content or ""
            finish_reason = response.choices[0].finish_reason or "stop"

            aggregated_content.append(content)
            total_tokens_in += response.usage.prompt_tokens
            total_tokens_out += response.usage.completion_tokens

            if finish_reason != "length":
                return "\n".join(part for part in aggregated_content if part).strip(), total_tokens_in, total_tokens_out

            conversation.append({"role": "assistant", "content": content})
            conversation.append(
                {
                    "role": "user",
                    "content": (
                        "CONTINUE. Continue exactly from the stopping point. "
                        "Do not repeat already emitted text and do not restart the answer."
                    ),
                }
            )

        logger.warning("DeepSeek continuation rounds exhausted; returning partial response.")
        return "\n".join(part for part in aggregated_content if part).strip(), total_tokens_in, total_tokens_out
    except RateLimitError:
        raise LimitExceeded("DeepSeek rate limit")
    except Exception as exc:
        raise ProviderError(f"DeepSeek error: {exc}")


async def _call_openai_format(
    provider: str,
    model: str,
    messages: list[dict],
    tools: list,
    max_tokens: int,
) -> tuple[str, Optional[dict], int, int]:
    from openai import AsyncOpenAI, RateLimitError
    from agents.tools.registry import to_openai_schema

    if provider == "deepseek":
        client = AsyncOpenAI(api_key=settings.deepseek_api_key, base_url="https://api.deepseek.com")
    elif provider == "codex":
        client = AsyncOpenAI(api_key=await _get_codex_token())
    else:
        raise ProviderError(f"Unknown provider: {provider}")

    kwargs = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    if tools:
        kwargs["tools"] = to_openai_schema(tools)
        kwargs["tool_choice"] = "auto"

    total_tokens_in = 0
    total_tokens_out = 0
    aggregated_content: list[str] = []
    conversation = list(messages)

    for _ in range(6):
        try:
            response = await client.chat.completions.create(**kwargs | {"messages": conversation})
        except RateLimitError:
            raise LimitExceeded(f"{provider} rate limit")
        except Exception as exc:
            raise ProviderError(f"{provider} error: {exc}")

        choice = response.choices[0]
        message = choice.message
        finish_reason = choice.finish_reason or "stop"
        total_tokens_in += response.usage.prompt_tokens
        total_tokens_out += response.usage.completion_tokens

        if message.tool_calls:
            tool_call = message.tool_calls[0]
            try:
                args = json.loads(tool_call.function.arguments)
            except Exception:
                args = {}
            return message.content or "", {"name": tool_call.function.name, "arguments": args}, total_tokens_in, total_tokens_out

        content = message.content or ""
        aggregated_content.append(content)
        if provider != "deepseek" or finish_reason != "length":
            return "\n".join(part for part in aggregated_content if part).strip(), None, total_tokens_in, total_tokens_out

        conversation.append({"role": "assistant", "content": content})
        conversation.append(
            {
                "role": "user",
                "content": (
                    "CONTINUE. Continue exactly from the stopping point. "
                    "Do not repeat already emitted text and do not restart the answer."
                ),
            }
        )

    return "\n".join(part for part in aggregated_content if part).strip(), None, total_tokens_in, total_tokens_out


async def _call_google_plain(messages: list[dict], model: str, max_tokens: int, api_key: str) -> tuple[str, int, int]:
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    client = genai.GenerativeModel(model_name=model, generation_config={"max_output_tokens": max_tokens})

    history = []
    last_user = ""
    for message in messages:
        if message["role"] == "system":
            last_user = message["content"]
        elif message["role"] == "user":
            last_user = (last_user + "\n\n" + message["content"]).strip() if last_user else message["content"]
        elif message["role"] == "assistant":
            if last_user:
                history.append({"role": "user", "parts": [last_user]})
                last_user = ""
            history.append({"role": "model", "parts": [message["content"]]})

    prompt = last_user or "Continue."
    try:
        response = await client.generate_content_async(history + [{"role": "user", "parts": [prompt]}])
        text = response.text
        return text, len(prompt.split()) * 2, len(text.split()) * 2
    except Exception as exc:
        if "quota" in str(exc).lower() or "limit" in str(exc).lower():
            raise LimitExceeded(f"Google quota: {exc}")
        raise ProviderError(f"Google error: {exc}")


async def _call_google_with_tools(
    model: str,
    messages: list[dict],
    tools: list,
    max_tokens: int,
) -> tuple[str, Optional[dict], int, int]:
    import google.generativeai as genai
    from agents.tools.registry import to_google_schema

    genai.configure(api_key=settings.google_ai_studio_key)
    client = genai.GenerativeModel(
        model_name=model,
        generation_config={"max_output_tokens": max_tokens, "temperature": 0.7},
        tools=to_google_schema(tools) if tools else None,
    )

    history = []
    last_user = ""
    for message in messages:
        if message["role"] in {"system", "user"}:
            last_user = (last_user + "\n\n" + (message.get("content") or "")).strip() if last_user else (message.get("content") or "")
        elif message["role"] == "assistant":
            if last_user:
                history.append({"role": "user", "parts": [last_user]})
                last_user = ""
            history.append({"role": "model", "parts": [message.get("content") or ""]})
        elif message["role"] == "tool":
            history.append({"role": "user", "parts": [f"Tool result: {message.get('content', '')}"]})

    prompt = last_user or "Continue."
    try:
        response = await client.generate_content_async(history + [{"role": "user", "parts": [prompt]}])
    except Exception as exc:
        if "quota" in str(exc).lower():
            raise LimitExceeded(f"Google quota: {exc}")
        raise ProviderError(f"Google error: {exc}")

    content = ""
    tool_call_data = None
    for part in response.candidates[0].content.parts:
        if getattr(part, "text", None):
            content += part.text
        elif getattr(part, "function_call", None):
            tool_call_data = {
                "name": part.function_call.name,
                "arguments": dict(part.function_call.args),
            }

    return content, tool_call_data, len(prompt.split()) * 2, len(content.split()) * 2


async def call_llm(
    provider: str,
    model: str,
    messages: list[dict],
    max_tokens: int = 4096,
    agent_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> str:
    start = time.time()
    approx_input_tokens = _estimate_message_tokens(messages)
    tokens_in = tokens_out = 0

    try:
        if provider == "deepseek":
            content, tokens_in, tokens_out = await _call_deepseek(messages, model, max_tokens, settings.deepseek_api_key)
        elif provider == "google":
            content, tokens_in, tokens_out = await _call_google_plain(
                messages, model, max_tokens, settings.google_ai_studio_key
            )
        elif provider == "codex":
            content, _tool, tokens_in, tokens_out = await _call_openai_format(
                provider="codex",
                model=model,
                messages=messages,
                tools=[],
                max_tokens=max_tokens,
            )
        else:
            raise ProviderError(f"Unknown provider: {provider}")
    finally:
        elapsed = round(time.time() - start, 2)
        logger.debug(
            f"[{agent_id}] {provider}/{model} | approx_in {approx_input_tokens} | actual {tokens_in}+{tokens_out} tok | {elapsed}s"
        )

    await _log_usage(agent_id, provider, model, tokens_in, tokens_out, task_id)
    return content


async def call_llm_with_tools(
    agent_id: str,
    task_id: Optional[str],
    messages: list[dict],
    tools: list,
    max_tokens: int = 2048,
    _provider_override: str = None,
    _model_override: str = None,
) -> Optional[dict]:
    if _provider_override and _model_override:
        provider, model = _provider_override, _model_override
    else:
        provider, model = await _get_agent_config(agent_id)

    start = time.time()
    approx_input_tokens = _estimate_message_tokens(messages)
    content = None
    tool_call_data = None
    tokens_in = tokens_out = 0

    try:
        if provider in {"deepseek", "codex"}:
            content, tool_call_data, tokens_in, tokens_out = await _call_openai_format(
                provider=provider,
                model=model,
                messages=messages,
                tools=tools,
                max_tokens=max_tokens,
            )
        elif provider == "google":
            content, tool_call_data, tokens_in, tokens_out = await _call_google_with_tools(
                model=model,
                messages=messages,
                tools=tools,
                max_tokens=max_tokens,
            )
        else:
            raise ProviderError(f"Unknown provider: {provider}")
    except LimitExceeded:
        if provider == "codex":
            account = await _get_active_codex_account()
            if account:
                switched = await _switch_codex_account(account["id"])
                if switched:
                    return await call_llm_with_tools(
                        agent_id=agent_id,
                        task_id=task_id,
                        messages=messages,
                        tools=tools,
                        max_tokens=max_tokens,
                    )
        raise
    finally:
        elapsed = round(time.time() - start, 2)
        logger.debug(
            f"[{agent_id}] {provider}/{model} | approx_in {approx_input_tokens} | actual {tokens_in}+{tokens_out} tok | {elapsed}s"
        )

    await _log_usage(agent_id, provider, model, tokens_in, tokens_out, task_id)

    if tool_call_data:
        return {
            "type": "tool_call",
            "tool_name": tool_call_data["name"],
            "tool_args": tool_call_data["arguments"],
            "thought": content or "",
        }

    return {"type": "text", "content": content or ""}


async def _log_usage(
    agent_id: Optional[str],
    provider: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    task_id: Optional[str],
):
    import uuid

    from core.database import AsyncSessionLocal
    from models import APIUsageLog

    rates = MODEL_COST_TABLE.get(model, MODEL_COST_TABLE.get(provider, {"in": 0, "out": 0}))
    cost = tokens_in * rates["in"] + tokens_out * rates["out"]

    async with AsyncSessionLocal() as db:
        db.add(
            APIUsageLog(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                provider=provider,
                model=model,
                tokens_input=tokens_in,
                tokens_output=tokens_out,
                cost_usd=cost,
                task_id=task_id,
            )
        )
        await db.commit()
