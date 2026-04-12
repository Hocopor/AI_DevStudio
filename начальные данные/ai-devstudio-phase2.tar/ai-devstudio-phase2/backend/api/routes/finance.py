from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timezone, timedelta
from core.database import get_db
from core.auth import get_current_user
from models import APIUsageLog, Notification

router = APIRouter(prefix="/finance", tags=["finance"])


def _period_start(period: str) -> datetime:
    now = datetime.now(timezone.utc)
    if period == "day":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # all — начало эпохи
    return datetime(2024, 1, 1, tzinfo=timezone.utc)


@router.get("/summary")
async def finance_summary(
    period: str = Query("month", regex="^(day|week|month|all)$"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    since = _period_start(period)

    # Расходы на AI
    ai_cost = await db.scalar(
        select(func.sum(APIUsageLog.cost_usd)).where(APIUsageLog.created_at >= since)
    ) or 0.0

    # Токены по провайдерам
    provider_rows = await db.execute(
        select(
            APIUsageLog.provider,
            func.sum(APIUsageLog.tokens_input).label("tokens_in"),
            func.sum(APIUsageLog.tokens_output).label("tokens_out"),
            func.sum(APIUsageLog.cost_usd).label("cost"),
            func.count(APIUsageLog.id).label("calls"),
        )
        .where(APIUsageLog.created_at >= since)
        .group_by(APIUsageLog.provider)
    )
    by_provider = [
        {
            "provider": r.provider,
            "tokens_in": r.tokens_in or 0,
            "tokens_out": r.tokens_out or 0,
            "cost_usd": float(r.cost or 0),
            "calls": r.calls,
        }
        for r in provider_rows
    ]

    # Расходы по агентам
    agent_rows = await db.execute(
        select(
            APIUsageLog.agent_id,
            func.sum(APIUsageLog.cost_usd).label("cost"),
            func.count(APIUsageLog.id).label("calls"),
        )
        .where(APIUsageLog.created_at >= since)
        .group_by(APIUsageLog.agent_id)
        .order_by(func.sum(APIUsageLog.cost_usd).desc())
    )
    by_agent = [
        {"agent_id": r.agent_id, "cost_usd": float(r.cost or 0), "calls": r.calls}
        for r in agent_rows
    ]

    # Динамика по дням (последние 30 дней)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    daily_rows = await db.execute(
        select(
            func.date_trunc("day", APIUsageLog.created_at).label("day"),
            func.sum(APIUsageLog.cost_usd).label("cost"),
            func.count(APIUsageLog.id).label("calls"),
        )
        .where(APIUsageLog.created_at >= thirty_days_ago)
        .group_by(func.date_trunc("day", APIUsageLog.created_at))
        .order_by(func.date_trunc("day", APIUsageLog.created_at))
    )
    daily = [
        {"day": r.day.strftime("%Y-%m-%d"), "cost_usd": float(r.cost or 0), "calls": r.calls}
        for r in daily_rows
    ]

    # Всего токенов
    total_tokens_in = await db.scalar(
        select(func.sum(APIUsageLog.tokens_input)).where(APIUsageLog.created_at >= since)
    ) or 0
    total_tokens_out = await db.scalar(
        select(func.sum(APIUsageLog.tokens_output)).where(APIUsageLog.created_at >= since)
    ) or 0

    return {
        "period": period,
        "since": since.isoformat(),
        "total_cost_usd": float(ai_cost),
        "total_tokens_in": total_tokens_in,
        "total_tokens_out": total_tokens_out,
        "total_tokens": total_tokens_in + total_tokens_out,
        "by_provider": by_provider,
        "by_agent": by_agent,
        "daily": daily,
    }


@router.get("/usage-log")
async def usage_log(
    limit: int = Query(100),
    provider: str = Query(None),
    agent_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    q = select(APIUsageLog).order_by(APIUsageLog.created_at.desc()).limit(limit)
    if provider:
        q = q.where(APIUsageLog.provider == provider)
    if agent_id:
        q = q.where(APIUsageLog.agent_id == agent_id)
    result = await db.execute(q)
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "agent_id": l.agent_id,
            "provider": l.provider,
            "model": l.model,
            "tokens_input": l.tokens_input,
            "tokens_output": l.tokens_output,
            "cost_usd": float(l.cost_usd),
            "task_id": l.task_id,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]
