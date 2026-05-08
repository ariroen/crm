from __future__ import annotations

"""
Контракт-61: Сервис операторов и задач.
"""

import logging
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Operator, Task, Candidate, OperatorRole, TaskStatus

logger = logging.getLogger(__name__)


class OperatorService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Операторы ──

    async def add_operator(self, user_id: int, name: str, role: OperatorRole = OperatorRole.OPERATOR) -> Operator:
        op = Operator(user_id=user_id, name=name, role=role)
        self.session.add(op)
        await self.session.commit()
        await self.session.refresh(op)
        logger.info("👤 Оператор добавлен: %s (user_id=%d)", name, user_id)
        return op

    async def get_by_user_id(self, user_id: int) -> Optional[Operator]:
        q = select(Operator).where(Operator.user_id == user_id)
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def get_by_id(self, op_id: int) -> Optional[Operator]:
        return await self.session.get(Operator, op_id)

    async def get_all(self, active_only: bool = True) -> List[Operator]:
        q = select(Operator)
        if active_only:
            q = q.where(Operator.active == True)
        q = q.order_by(Operator.name)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def deactivate(self, op_id: int) -> Optional[Operator]:
        op = await self.get_by_id(op_id)
        if op:
            op.active = False
            await self.session.commit()
            await self.session.refresh(op)
        return op

    async def is_admin(self, user_id: int) -> bool:
        op = await self.get_by_user_id(user_id)
        return op is not None and op.role == OperatorRole.ADMIN

    # ── Закрепление кандидатов ──

    async def assign_candidate(self, candidate_id: int, operator_id: int) -> Optional[Candidate]:
        candidate = await self.session.get(Candidate, candidate_id)
        if candidate:
            candidate.assigned_operator_id = operator_id
            await self.session.commit()
            await self.session.refresh(candidate)
            logger.info("🔗 Кандидат #%d → Оператор #%d", candidate_id, operator_id)
        return candidate

    async def get_operator_candidates(self, operator_id: int) -> List[Candidate]:
        q = select(Candidate).where(
            Candidate.assigned_operator_id == operator_id,
            Candidate.archived == False,
        ).order_by(Candidate.created_at.desc())
        result = await self.session.execute(q)
        return list(result.scalars().all())

    # ── Задачи ──

    async def create_task(
        self,
        assigned_to: int,
        assigned_by: int,
        title: str,
        description: str = None,
        candidate_id: int = None,
        deadline: datetime = None,
    ) -> Task:
        task = Task(
            assigned_to=assigned_to,
            assigned_by=assigned_by,
            title=title,
            description=description,
            candidate_id=candidate_id,
            deadline=deadline,
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        logger.info("📋 Задача #%d создана для оператора #%d", task.id, assigned_to)
        return task

    async def get_tasks_for_operator(self, operator_id: int, include_done: bool = False) -> List[Task]:
        q = select(Task).where(Task.assigned_to == operator_id)
        if not include_done:
            q = q.where(Task.status != TaskStatus.DONE)
        q = q.order_by(Task.created_at.desc())
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def update_task_status(self, task_id: int, status: TaskStatus) -> Optional[Task]:
        task = await self.session.get(Task, task_id)
        if task:
            task.status = status
            await self.session.commit()
            await self.session.refresh(task)
        return task

    async def get_tasks_with_deadlines(self) -> List[Task]:
        """Задачи с дедлайнами, ещё не выполненные."""
        q = select(Task).where(
            Task.deadline.isnot(None),
            Task.status != TaskStatus.DONE,
        ).order_by(Task.deadline)
        result = await self.session.execute(q)
        return list(result.scalars().all())
