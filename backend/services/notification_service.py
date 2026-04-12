import uuid
import time
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from models import Notification
from services.ws_manager import ws_manager


PRIORITY_EMOJI = {
    "critical": "🔴",
    "high":     "🟡",
    "medium":   "🟢",
    "info":     "📊",
}

# Какие приоритеты слать в VK
VK_SEND_PRIORITIES = {"critical", "high"}


async def notify(
    db: AsyncSession,
    type: str,
    title: str,
    priority: str = "medium",
    body: Optional[str] = None,
    task_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> Notification:
    """Создать уведомление в БД, отправить WS + VK если нужно"""

    n = Notification(
        id=str(uuid.uuid4()),
        type=type,
        priority=priority,
        title=title,
        body=body,
        task_id=task_id,
        project_id=project_id,
    )
    db.add(n)
    await db.commit()
    await db.refresh(n)

    # WS broadcast
    await ws_manager.broadcast({
        "event": "notification",
        "notification": {
            "id": n.id,
            "type": n.type,
            "priority": n.priority,
            "title": n.title,
            "body": n.body,
        }
    })

    # VK — только критичные и высокие
    if priority in VK_SEND_PRIORITIES:
        await _send_vk(n)

    return n


async def _send_vk(notification: Notification):
    """Отправить личное сообщение владельцу через VK API"""
    try:
        import vk_api as vk_lib
        from core.config import settings

        emoji = PRIORITY_EMOJI.get(notification.priority, "📢")
        text = f"{emoji} AI DevStudio\n\n{notification.title}"
        if notification.body:
            text += f"\n\n{notification.body}"

        session = vk_lib.VkApi(token=settings.vk_api_token)
        vk = session.get_api()
        vk.messages.send(
            user_id=settings.vk_owner_user_id,
            message=text,
            random_id=int(time.time() * 1000),
        )

        # Отметить в БД что VK отправлен
        from core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            from sqlalchemy import update
            await db.execute(
                update(Notification)
                .where(Notification.id == notification.id)
                .values(vk_sent=True)
            )
            await db.commit()

        logger.info(f"VK уведомление отправлено: {notification.title}")

    except Exception as e:
        logger.error(f"Ошибка отправки VK: {e}")
