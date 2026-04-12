from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import Optional
from core.database import get_db
from core.auth import get_current_user
from models import CodexAccount
import uuid

router = APIRouter(prefix="/codex-accounts", tags=["codex"])


class AccountCreate(BaseModel):
    label: str
    oauth_token: str
    priority: int = 1


class AccountUpdate(BaseModel):
    label: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("")
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    result = await db.execute(select(CodexAccount).order_by(CodexAccount.priority))
    accounts = result.scalars().all()
    return [
        {
            "id": a.id, "label": a.label, "priority": a.priority,
            "is_active": a.is_active, "is_current": a.is_current,
            "limit_info": a.limit_info, "created_at": a.created_at,
            # Токен не отдаём в API
        }
        for a in accounts
    ]


@router.post("", status_code=201)
async def add_account(
    body: AccountCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    # Если это первый аккаунт — сделать его текущим
    existing = await db.scalar(select(CodexAccount).limit(1))
    is_first = existing is None

    account = CodexAccount(
        id=str(uuid.uuid4()),
        label=body.label,
        oauth_token_encrypted=body.oauth_token,  # TODO: encrypt in prod
        priority=body.priority,
        is_active=True,
        is_current=is_first,
    )
    db.add(account)
    await db.commit()
    return {"id": account.id, "label": account.label}


@router.put("/{account_id}")
async def update_account(
    account_id: str,
    body: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    account = await db.get(CodexAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    await db.commit()
    return {"detail": "Обновлено"}


@router.post("/{account_id}/set-current")
async def set_current_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Вручную переключить активный аккаунт"""
    await db.execute(update(CodexAccount).values(is_current=False))
    await db.execute(update(CodexAccount).where(CodexAccount.id == account_id).values(is_current=True))
    await db.commit()
    return {"detail": "Переключено"}


@router.delete("/{account_id}", status_code=204)
async def delete_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    account = await db.get(CodexAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    await db.delete(account)
    await db.commit()
