from __future__ import annotations

"""
Контракт-61: Сервис управления кандидатами.
CRUD + бизнес-логика воронки.
"""

import logging
from datetime import datetime, date, timedelta

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Candidate,
    CandidatePhoto,
    MedicalStatus,
    TicketStatus,
    RegistrationStatus,
    Category,
)

logger = logging.getLogger(__name__)


class CandidateService:
    """Бизнес-логика работы с кандидатами."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── CREATE ────────────────────────────────────────────

    async def create(
        self,
        full_name: str,
        created_by: int,
        phone: str | None = None,
        source: str | None = None,
        ticket_status: str | None = None,
        arrival_date: datetime | None = None,
        medical_status: str | None = None,
        notes: str | None = None,
    ) -> Candidate:
        """Создать нового кандидата."""
        candidate = Candidate(
            full_name=full_name,
            phone=phone,
            source=source,
            ticket_status=TicketStatus(ticket_status) if ticket_status else TicketStatus.NEEDED,
            arrival_date=arrival_date,
            medical_status=MedicalStatus(medical_status) if medical_status else MedicalStatus.NOT_STARTED,
            registration_status=RegistrationStatus.NONE,
            notes=notes,
            created_by=created_by,
        )
        self.session.add(candidate)
        await self.session.commit()
        await self.session.refresh(candidate)
        logger.info("✅ Создан кандидат: %s (ID: %d)", candidate.full_name, candidate.id)
        return candidate

    # ── READ ──────────────────────────────────────────────

    async def get_by_id(self, candidate_id: int) -> Candidate | None:
        """Получить кандидата по ID."""
        return await self.session.get(Candidate, candidate_id)

    async def list_active(self, created_by: int | None = None) -> list[Candidate]:
        """Список активных (не архивных) кандидатов."""
        query = (
            select(Candidate)
            .where(Candidate.archived == False)
            .order_by(Candidate.created_at.desc())
        )
        if created_by is not None:
            query = query.where(Candidate.created_by == created_by)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_all(self, archived: bool = False) -> list[Candidate]:
        """Все кандидаты (алиас для list_active без фильтра по user)."""
        return await self.list_active()

    async def get_stats(self) -> dict:
        """Сводная статистика по кандидатам."""
        candidates = await self.list_active()
        return {
            "total": len(candidates),
            "bought": sum(1 for c in candidates if c.ticket_status == TicketStatus.BOUGHT),
            "transit": sum(1 for c in candidates if c.ticket_status == TicketStatus.IN_TRANSIT),
            "arrived": sum(1 for c in candidates if c.ticket_status == TicketStatus.ARRIVED),
            "fit": sum(1 for c in candidates if c.medical_status == MedicalStatus.FIT),
            "departed": sum(1 for c in candidates if c.registration_status == RegistrationStatus.DEPARTED),
        }

    async def search(self, query: str) -> list[Candidate]:
        """Поиск кандидата по имени или телефону."""
        pattern = f"%{query}%"
        stmt = (
            select(Candidate)
            .where(
                Candidate.archived == False,
                or_(
                    Candidate.full_name.ilike(pattern),
                    Candidate.phone.ilike(pattern),
                ),
            )
            .order_by(Candidate.full_name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ── UPDATE STATUSES ───────────────────────────────────

    async def update_ticket_status(
        self, candidate_id: int, status: TicketStatus, arrival_date: datetime | None = None
    ) -> Candidate | None:
        """Обновить статус билета."""
        candidate = await self.get_by_id(candidate_id)
        if not candidate:
            return None
        candidate.ticket_status = status
        if arrival_date:
            candidate.arrival_date = arrival_date
        await self.session.commit()
        await self.session.refresh(candidate)
        logger.info("🎫 Билет %s → %s", candidate.full_name, status.value)
        return candidate

    async def cycle_ticket_status(self, candidate_id: int) -> Candidate | None:
        """Циклическое переключение статуса билета (кнопка)."""
        candidate = await self.get_by_id(candidate_id)
        if not candidate:
            return None
        cycle = [TicketStatus.NEEDED, TicketStatus.BOUGHT, TicketStatus.IN_TRANSIT, TicketStatus.ARRIVED]
        idx = cycle.index(candidate.ticket_status)
        candidate.ticket_status = cycle[(idx + 1) % len(cycle)]
        await self.session.commit()
        await self.session.refresh(candidate)
        return candidate

    async def update_medical_status(
        self, candidate_id: int, status: MedicalStatus
    ) -> Candidate | None:
        """Обновить статус медицины."""
        candidate = await self.get_by_id(candidate_id)
        if not candidate:
            return None
        candidate.medical_status = status
        await self.session.commit()
        await self.session.refresh(candidate)
        logger.info("🏥 Медицина %s → %s", candidate.full_name, status.value)
        return candidate

    async def cycle_medical_status(self, candidate_id: int) -> Candidate | None:
        """Циклическое переключение статуса медицины."""
        candidate = await self.get_by_id(candidate_id)
        if not candidate:
            return None
        cycle = [
            MedicalStatus.NOT_STARTED,
            MedicalStatus.IN_PROGRESS,
            MedicalStatus.EXTRA_TESTS,
            MedicalStatus.FIT,
            MedicalStatus.UNFIT,
        ]
        idx = cycle.index(candidate.medical_status)
        candidate.medical_status = cycle[(idx + 1) % len(cycle)]
        await self.session.commit()
        await self.session.refresh(candidate)
        return candidate

    async def cycle_registration_status(self, candidate_id: int) -> Candidate | None:
        """Циклическое переключение статуса оформления."""
        candidate = await self.get_by_id(candidate_id)
        if not candidate:
            return None
        cycle = [
            RegistrationStatus.NONE,
            RegistrationStatus.ARRIVED,
            RegistrationStatus.MEDICAL,
            RegistrationStatus.ORDERED,
            RegistrationStatus.DEPARTED
        ]
        idx = cycle.index(candidate.registration_status)
        new_status = cycle[(idx + 1) % len(cycle)]
        candidate.registration_status = new_status
        
        # Если статус "Убыл" — переносим в категорию "Убывшие"
        if new_status == RegistrationStatus.DEPARTED:
            # Ищем категорию
            result = await self.session.execute(
                select(Category).where(Category.name == "Убывшие")
            )
            cat = result.scalar_one_or_none()
            if not cat:
                # Создаем, если нет
                cat = Category(name="Убывшие", emoji="📝")
                self.session.add(cat)
                await self.session.flush()
            candidate.category_id = cat.id

        await self.session.commit()
        await self.session.refresh(candidate)
        return candidate

    async def toggle_gic_status(self, candidate_id: int) -> Candidate | None:
        """Переключить статус ГИЦ."""
        candidate = await self.get_by_id(candidate_id)
        if not candidate:
            return None
        candidate.gic_status = not candidate.gic_status
        await self.session.commit()
        await self.session.refresh(candidate)
        return candidate

    async def delete(self, candidate_id: int) -> bool:
        """Удалить кандидата полностью."""
        candidate = await self.get_by_id(candidate_id)
        if not candidate:
            return False
        await self.session.delete(candidate)
        await self.session.commit()
        logger.info("🗑 Кандидат #%d удален", candidate_id)
        return True

    # ── ARCHIVE ───────────────────────────────────────────

    async def archive(self, candidate_id: int) -> Candidate | None:
        """Отправить кандидата в архив."""
        candidate = await self.get_by_id(candidate_id)
        if not candidate:
            return None
        candidate.archived = True
        await self.session.commit()
        await self.session.refresh(candidate)
        return candidate

    # ── PHOTOS ────────────────────────────────────────────

    async def add_photo(
        self,
        candidate_id: int,
        file_id: str,
        file_type: str = "ticket",
        description: str | None = None,
    ) -> CandidatePhoto:
        """Прикрепить фото к кандидату."""
        photo = CandidatePhoto(
            candidate_id=candidate_id,
            file_id=file_id,
            file_type=file_type,
            description=description,
        )
        self.session.add(photo)
        await self.session.commit()
        await self.session.refresh(photo)
        logger.info("🖼 Фото добавлено к кандидату #%d", candidate_id)
        return photo

    async def get_photos(self, candidate_id: int) -> list[CandidatePhoto]:
        """Получить все фото кандидата."""
        result = await self.session.execute(
            select(CandidatePhoto)
            .where(CandidatePhoto.candidate_id == candidate_id)
            .order_by(CandidatePhoto.created_at.desc())
        )
        return list(result.scalars().all())

    # ── AI-POWERED CREATE/UPDATE ──────────────────────────

    async def process_ai_data(self, intent: str, data: dict, user_id: int) -> tuple[str, Candidate | None]:
        """
        Обработать данные от AI-аналитика.

        Returns:
            (message, candidate) — текстовый ответ и объект кандидата (если есть).
        """
        if intent == "create_candidate":
            name = data.get("full_name")
            if not name:
                return "⚠️ ИИ не смог распознать имя кандидата.", None

            arrival = None
            if data.get("arrival_date"):
                try:
                    arrival = datetime.strptime(data["arrival_date"], "%Y-%m-%d")
                except ValueError:
                    pass

            candidate = await self.create(
                full_name=name,
                created_by=user_id,
                phone=data.get("phone"),
                source=data.get("source"),
                ticket_status=data.get("ticket_status"),
                arrival_date=arrival,
                medical_status=data.get("medical_status"),
                notes=data.get("notes"),
            )
            return f"✅ Кандидат **{candidate.full_name}** создан (ID: {candidate.id}).", candidate

        elif intent == "update_candidate":
            # Комбинированное обновление — применить все доступные поля
            name = data.get("full_name")
            if not name:
                return "⚠️ ИИ не смог определить, о ком идет речь.", None
            candidates = await self.search(name)
            if not candidates:
                return f"⚠️ Кандидат «{name}» не найден в базе.", None
            candidate = candidates[0]
            updates = []
            if data.get("ticket_status"):
                arrival = None
                if data.get("arrival_date"):
                    try:
                        arrival = datetime.strptime(data["arrival_date"], "%Y-%m-%d")
                    except ValueError:
                        pass
                await self.update_ticket_status(candidate.id, TicketStatus(data["ticket_status"]), arrival)
                updates.append(f"🎫 Билет → **{data['ticket_status']}**")
            if data.get("medical_status"):
                await self.update_medical_status(candidate.id, MedicalStatus(data["medical_status"]))
                updates.append(f"🏥 Медицина → **{data['medical_status']}**")
            if data.get("registration_status"):
                await self.cycle_registration_status(candidate.id) # Simplified for now
                updates.append(f"📝 Оформление → **{data['registration_status']}**")
            if not updates:
                return "⚠️ Недостаточно данных для обновления.", candidate
            return f"✅ {candidate.full_name} обновлён:\n" + "\n".join(updates), candidate

        elif intent in ("update_ticket", "update_medical", "update_registration"):
            name = data.get("full_name")
            if not name:
                return "⚠️ ИИ не смог определить, о ком идет речь.", None

            candidates = await self.search(name)
            if not candidates:
                return f"⚠️ Кандидат «{name}» не найден в базе.", None

            candidate = candidates[0]  # Берём первое совпадение

            if intent == "update_ticket" and data.get("ticket_status"):
                arrival = None
                if data.get("arrival_date"):
                    try:
                        arrival = datetime.strptime(data["arrival_date"], "%Y-%m-%d")
                    except ValueError:
                        pass
                await self.update_ticket_status(
                    candidate.id, TicketStatus(data["ticket_status"]), arrival
                )
                return f"🎫 Билет {candidate.full_name} → **{data['ticket_status']}**.", candidate

            elif intent == "update_medical" and data.get("medical_status"):
                await self.update_medical_status(
                    candidate.id, MedicalStatus(data["medical_status"])
                )
                return f"🏥 Медицина {candidate.full_name} → **{data['medical_status']}**.", candidate

            elif intent == "update_registration" and data.get("registration_status"):
                await self.update_registration_status(
                    candidate.id, RegistrationStatus(data["registration_status"])
                )
                return f"🪖 Обучение {candidate.full_name} → **{data['registration_status']}**.", candidate

            return "⚠️ Недостаточно данных для обновления.", candidate

        elif intent == "mass_action":
            from app.db.models import Task, Operator
            from sqlalchemy import select as sel
            from datetime import date
            
            filter_type = data.get("mass_filter")
            task_text = data.get("mass_task")
            
            query = sel(Candidate).where(Candidate.archived == False)
            if filter_type == "arriving_tomorrow":
                tomorrow = date.today() + timedelta(days=1)
                query = query.where(func.date(Candidate.arrival_date) == tomorrow)
            elif filter_type == "no_ticket":
                query = query.where(Candidate.ticket_status == TicketStatus.NEEDED)
            elif filter_type == "pending_medical":
                query = query.where(Candidate.medical_status == MedicalStatus.IN_PROGRESS)
            
            result = await self.session.execute(query)
            candidates = list(result.scalars().all())
            
            if not candidates:
                return f"🔍 По фильтру «{filter_type}» кандидатов не найдено.", None
            
            if task_text:
                # Создаем задачи для всех найденных
                from app.services.operator_service import OperatorService
                osvc = OperatorService(self.session)
                creator = await osvc.get_by_user_id(user_id)
                creator_id = creator.id if creator else 1 # Default to admin if not found
                
                tasks_created = 0
                for cand in candidates:
                    # Закрепляем за тем же оператором, кто просил, или за тем кто уже закреплен
                    target_op = cand.assigned_operator_id or creator_id
                    await osvc.create_task(
                        assigned_to=target_op,
                        assigned_by=creator_id,
                        title=task_text,
                        candidate_id=cand.id
                    )
                    tasks_created += 1
                return f"✅ Массовое действие: найдено {len(candidates)}, создано {tasks_created} задач.", candidates[0]
            
            return f"🔍 Найдено {len(candidates)} канд. по фильтру «{filter_type}».", candidates[0]

        return "⚠️ Не удалось распознать команду. Попробуйте иначе.", None
