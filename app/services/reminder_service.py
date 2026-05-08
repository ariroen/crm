from __future__ import annotations

"""
Контракт-61: Сервис напоминаний.
APScheduler для планирования + проверка БД.
"""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Reminder

logger = logging.getLogger(__name__)


class ReminderService:
    """Управление напоминаниями."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        remind_at: datetime,
        message: str,
        candidate_id: int | None = None,
    ) -> Reminder:
        """Создать напоминание."""
        reminder = Reminder(
            user_id=user_id,
            remind_at=remind_at,
            message=message,
            candidate_id=candidate_id,
            sent=False,
        )
        self.session.add(reminder)
        await self.session.commit()
        await self.session.refresh(reminder)
        logger.info("⏰ Напоминание создано: %s в %s", message[:50], remind_at)
        return reminder

    async def get_pending(self) -> list[Reminder]:
        """Получить все несработавшие напоминания, время которых наступило."""
        now = datetime.now()
        result = await self.session.execute(
            select(Reminder)
            .where(Reminder.sent == False, Reminder.remind_at <= now)
            .order_by(Reminder.remind_at)
        )
        return list(result.scalars().all())

    async def mark_sent(self, reminder_id: int) -> None:
        """Пометить напоминание как отправленное."""
        reminder = await self.session.get(Reminder, reminder_id)
        if reminder:
            reminder.sent = True
            await self.session.commit()

    async def get_user_reminders(self, user_id: int) -> list[Reminder]:
        """Получить активные напоминания пользователя."""
        result = await self.session.execute(
            select(Reminder)
            .where(Reminder.user_id == user_id, Reminder.sent == False)
            .order_by(Reminder.remind_at)
        )
        return list(result.scalars().all())

    async def get_active(self, user_id: int) -> list[Reminder]:
        """Алиас для get_user_reminders."""
        return await self.get_user_reminders(user_id)

    async def delete(self, reminder_id: int) -> bool:
        """Удалить напоминание."""
        reminder = await self.session.get(Reminder, reminder_id)
        if reminder:
            await self.session.delete(reminder)
            await self.session.commit()
            return True
        return False
