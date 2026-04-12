from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from core.database import get_db
from core.auth import get_current_user
from models import Notification
from schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    is_read: bool = Query(None),
    limit: int = Query(50),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    q = select(Notification).order_by(Notification.created_at.desc()).limit(limit)
    if is_read is not None:
        q = q.where(Notification.is_read == is_read)
    result = await db.execute(q)
    return result.scalars().all()


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id)
        .values(is_read=True)
    )
    await db.commit()
    return {"detail": "Отмечено как прочитанное"}


@router.put("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    await db.execute(
        update(Notification).where(Notification.is_read == False).values(is_read=True)
    )
    await db.commit()
    return {"detail": "Все уведомления отмечены как прочитанные"}


@router.get("/unread-count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    from sqlalchemy import func
    count = await db.scalar(
        select(func.count()).where(Notification.is_read == False)
    )
    return {"count": count or 0}
