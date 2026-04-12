"""
Провайдер-агностик слой для вызова LLM.
Поддерживает: DeepSeek, Google AI Studio, Codex OAuth (мультиаккаунт).
"""
import json
import time
import asyncio
from typing import Optional
from loguru import logger
from core.config import settings


class LimitExceeded(Exception):
    pass


class ProviderError(Exception):
    pass


# ── DeepSeek ─────────────────────────────────────────────────

async def _call_deepseek(
    messages: list[dict],
    model: str,
    max_tokens: int,
    api_key: str,
) -> tuple[str, int, int]:
    from openai import AsyncOpenAI, RateLimitError
    client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    try:
        resp = await client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens, temperature=0.7,
        )
        content = resp.choices[0].message.content or ""
        return content, resp.usage.prompt_tokens, resp.usage.completion_tokens
    except RateLimitError:
        raise LimitExceeded("DeepSeek rate limit")
    except Exception as e:
        raise ProviderError(f"DeepSeek error: {e}")


# ── Google AI Studio ──────────────────────────────────────────

async def _call_google(
    messages: list[dict],
    model: str,
    max_tokens: int,
    api_key: str,
) -> tuple[str, int, int]:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    client = genai.GenerativeModel(
        model_name=model,
        generation_config={"max_output_tokens": max_tokens},
    )
    # Конвертация messages в Google формат
    history = []
    last_user = ""
    for m in messages:
        if m["role"] == "system":
            last_user = m["content"]
        elif m["role"] == "user":
            last_user = (last_user + "\n\n" + m["content"]).strip() if last_user else m["content"]
        elif m["role"] == "assistant":
            if last_user:
                history.append({"role": "user", "parts": [last_user]})
                last_user = ""
            history.append({"role": "model", "parts": [m["content"]]})

    prompt = last_user or "Продолжи."
    try:
        response = await client.generate_content_async(
            history + [{"role": "user", "parts": [prompt]}]
        )
        text = response.text
        # Google не всегда отдаёт точные токены
        tokens_in = len(prompt.split()) * 2
        tokens_out = len(text.split()) * 2
        return text, tokens_in, tokens_out
    except Exception as e:
        if "quota" in str(e).lower() or "limit" in str(e).lower():
            raise LimitExceeded(f"Google quota: {e}")
        raise ProviderError(f"Google error: {e}")


# ── Codex OAuth мультиаккаунт ─────────────────────────────────

async def _get_active_codex_account() -> Optional[dict]:
    """Вернуть активный Codex аккаунт из БД"""
    from core.database import AsyncSessionLocal
    from models import CodexAccount
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CodexAccount)
            .where(CodexAccount.is_active == True, CodexAccount.is_current == True)
            .limit(1)
        )
        acc = result.scalar_one_or_none()
        if acc:
            return {"id": acc.id, "token": acc.oauth_token_encrypted, "label": acc.label}
    return None


async def _switch_codex_account(failed_id: str) -> Optional[dict]:
    """Переключить на следующий Codex аккаунт по приоритету"""
    from core.database import AsyncSessionLocal
    from models import CodexAccount
    from sqlalchemy import select, update

    async with AsyncSessionLocal() as db:
        # Снять флаг current с текущего
        await db.execute(
            update(CodexAccount).where(CodexAccount.id == failed_id).values(is_current=False)
        )
        # Найти следующий по приоритету
        result = await db.execute(
            select(CodexAccount)
            .where(CodexAccount.is_active == True, CodexAccount.is_current == False)
            .order_by(CodexAccount.priority.asc())
            .limit(1)
        )
        next_acc = result.scalar_one_or_none()
        if next_acc:
            await db.execute(
                update(CodexAccount).where(CodexAccount.id == next_acc.id).values(is_current=True)
            )
            await db.commit()
            logger.warning(f"Codex: переключение на аккаунт '{next_acc.label}'")
            # Уведомление
            from services.notification_service import notify
            await notify(
                db=db,
                type="provider_limit",
                priority="high",
                title=f"Codex: переключение аккаунта",
                body=f"Лимит исчерпан. Переключились на '{next_acc.label}'.",
            )
            return {"id": next_acc.id, "token": next_acc.oauth_token_encrypted, "label": next_acc.label}
        else:
            await db.commit()
            logger.error("Codex: все аккаунты исчерпаны!")
            return None


async def _call_codex(
    messages: list[dict],
    model: str,
    max_tokens: int,
) -> tuple[str, int, int]:
    """Вызов Codex OAuth с авто-переключением аккаунта"""
    import httpx

    account = await _get_active_codex_account()
    if not account:
        raise ProviderError("Нет активных Codex аккаунтов")

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {account['token']}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model or "gpt-4o",
                        "messages": messages,
                        "max_tokens": max_tokens,
                    },
                )

            if resp.status_code == 429 or (resp.status_code == 200 and "rate_limit" in resp.text):
                logger.warning(f"Codex limit на аккаунте {account['label']}")
                account = await _switch_codex_account(account["id"])
                if not account:
                    raise LimitExceeded("Все Codex аккаунты исчерпаны")
                continue

            if resp.status_code != 200:
                raise ProviderError(f"Codex HTTP {resp.status_code}: {resp.text[:200]}")

            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return content, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)

        except (LimitExceeded, ProviderError):
            raise
        except Exception as e:
            if attempt == 2:
                raise ProviderError(f"Codex error: {e}")
            await asyncio.sleep(2 ** attempt)

    raise ProviderError("Codex: превышено число попыток")


# ── Главная точка входа ───────────────────────────────────────

async def call_llm(
    provider: str,
    model: str,
    messages: list[dict],
    max_tokens: int = 4096,
    agent_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> str:
    """
    Единая точка вызова LLM.
    Логирует использование токенов и стоимость.
    """
    start = time.time()
    content = ""
    tokens_in = tokens_out = 0

    try:
        if provider == "deepseek":
            content, tokens_in, tokens_out = await _call_deepseek(
                messages, model, max_tokens, settings.deepseek_api_key
            )
        elif provider == "google":
            content, tokens_in, tokens_out = await _call_google(
                messages, model, max_tokens, settings.google_ai_studio_key
            )
        elif provider == "codex":
            content, tokens_in, tokens_out = await _call_codex(messages, model, max_tokens)
        else:
            raise ProviderError(f"Неизвестный провайдер: {provider}")

    except LimitExceeded:
        logger.error(f"[{agent_id}] Лимит провайдера {provider}")
        raise
    except ProviderError:
        raise
    finally:
        elapsed = round(time.time() - start, 2)
        logger.debug(f"[{agent_id}] {provider}/{model} | {tokens_in}+{tokens_out} tok | {elapsed}s")

    # Логируем использование
    await _log_usage(agent_id, provider, model, tokens_in, tokens_out, task_id)

    return content


# Стоимости ($/1k токенов, приблизительно)
COST_TABLE = {
    "deepseek": {"in": 0.00000014, "out": 0.00000028},
    "deepseek-reasoner": {"in": 0.00000055, "out": 0.00000219},
    "google": {"in": 0.000000075, "out": 0.0000003},
    "codex": {"in": 0.0000025, "out": 0.00001},
}


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

    rates = COST_TABLE.get(model, COST_TABLE.get(provider, {"in": 0, "out": 0}))
    cost = tokens_in * rates["in"] + tokens_out * rates["out"]

    async with AsyncSessionLocal() as db:
        log = APIUsageLog(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            provider=provider,
            model=model,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            cost_usd=cost,
            task_id=task_id,
        )
        db.add(log)
        await db.commit()
