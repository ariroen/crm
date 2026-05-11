"""
Контракт-61: Модели базы данных.

Candidate      — карточка кандидата (воронка).
CandidatePhoto — скриншоты (билеты, чеки).
Reminder       — напоминания.
AdPost         — рекламные размещения.
Operator       — операторы системы.
Task           — задачи для операторов.
"""

import enum
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# ── Enum-статусы ──────────────────────────────────────────────

class TicketStatus(str, enum.Enum):
    NEEDED = "needed"
    BOUGHT = "bought"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"


class MedicalStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    EXTRA_TESTS = "extra_tests"
    FIT = "fit"
    UNFIT = "unfit"


class TrainingStatus(str, enum.Enum):
    NONE = "none"
    ASSIGNED = "assigned"
    DEPARTED = "departed"


class OperatorRole(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"


class TaskStatus(str, enum.Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    DONE = "done"


# ── Модели ────────────────────────────────────────────────────

class Operator(Base):
    """Оператор системы (пользователь бота)."""

    __tablename__ = "operators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[OperatorRole] = mapped_column(
        Enum(OperatorRole), default=OperatorRole.OPERATOR, nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Связи
    candidates: Mapped[List["Candidate"]] = relationship(
        back_populates="operator", lazy="selectin"
    )
    tasks_assigned: Mapped[List["Task"]] = relationship(
        back_populates="assignee", foreign_keys="Task.assigned_to", lazy="selectin"
    )
    tasks_created: Mapped[List["Task"]] = relationship(
        back_populates="creator", foreign_keys="Task.assigned_by", lazy="selectin"
    )

    @property
    def role_emoji(self) -> str:
        return "👑" if self.role == OperatorRole.ADMIN else "👤"

    def __repr__(self) -> str:
        return "<Operator #{} {} ({})>".format(self.id, self.name, self.role.value)


class Candidate(Base):
    """Карточка кандидата на военную службу."""

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    ticket_status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus), default=TicketStatus.NEEDED, nullable=False
    )
    arrival_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    medical_status: Mapped[MedicalStatus] = mapped_column(
        Enum(MedicalStatus), default=MedicalStatus.NOT_STARTED, nullable=False
    )

    training_status: Mapped[TrainingStatus] = mapped_column(
        Enum(TrainingStatus), default=TrainingStatus.NONE, nullable=False
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)

    # Закрепление за оператором
    assigned_operator_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("operators.id", ondelete="SET NULL"), nullable=True
    )
    # Категория
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Связи
    operator: Mapped[Optional["Operator"]] = relationship(back_populates="candidates", lazy="selectin")
    category: Mapped[Optional["Category"]] = relationship(back_populates="candidates", lazy="selectin")
    photos: Mapped[List["CandidatePhoto"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", lazy="selectin"
    )
    reminders: Mapped[List["Reminder"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", lazy="selectin"
    )
    tasks: Mapped[List["Task"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def ticket_emoji(self) -> str:
        return {
            TicketStatus.NEEDED: "🎫❌",
            TicketStatus.BOUGHT: "🎫💰",
            TicketStatus.IN_TRANSIT: "🎫🚂",
            TicketStatus.ARRIVED: "🎫✅",
        }.get(self.ticket_status, "🎫❓")

    @property
    def medical_emoji(self) -> str:
        return {
            MedicalStatus.NOT_STARTED: "🏥❌",
            MedicalStatus.IN_PROGRESS: "🏥⏳",
            MedicalStatus.EXTRA_TESTS: "🏥🔬",
            MedicalStatus.FIT: "🏥✅",
            MedicalStatus.UNFIT: "🏥🚫",
        }.get(self.medical_status, "🏥❓")

    @property
    def training_emoji(self) -> str:
        return {
            TrainingStatus.NONE: "🪖❌",
            TrainingStatus.ASSIGNED: "🪖📋",
            TrainingStatus.DEPARTED: "🪖✅",
        }.get(self.training_status, "🪖❓")

    @property
    def status_line(self) -> str:
        return "{} | {} | {} | {}".format(
            self.full_name, self.ticket_emoji, self.medical_emoji, self.training_emoji
        )

    def __repr__(self) -> str:
        return "<Candidate #{} {}>".format(self.id, self.full_name)


class CandidatePhoto(Base):
    """Фото/скриншот, привязанный к кандидату."""

    __tablename__ = "candidate_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), default="ticket", nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    candidate: Mapped["Candidate"] = relationship(back_populates="photos")

    def __repr__(self) -> str:
        return "<Photo #{} for Candidate #{}>".format(self.id, self.candidate_id)


class Reminder(Base):
    """Напоминание."""

    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    remind_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    candidate: Mapped[Optional["Candidate"]] = relationship(back_populates="reminders")

    def __repr__(self) -> str:
        return "<Reminder #{} at {}>".format(self.id, self.remind_at)


class AdPost(Base):
    """Рекламное размещение (пост на канале)."""

    __tablename__ = "ad_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    channel_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    post_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    post_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cost: Mapped[Optional[float]] = mapped_column(Float, default=0, nullable=True)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    candidates_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    @property
    def cpl(self) -> str:
        """Cost Per Lead."""
        if self.candidates_count and self.cost:
            return "{:.0f}₽".format(self.cost / self.candidates_count)
        return "—"

    @property
    def cpc(self) -> str:
        """Cost Per Click."""
        if self.clicks and self.cost:
            return "{:.0f}₽".format(self.cost / self.clicks)
        return "—"

    def __repr__(self) -> str:
        return "<AdPost #{} {}>".format(self.id, self.channel_name)


class Task(Base):
    """Задача для оператора."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assigned_to: Mapped[int] = mapped_column(
        Integer, ForeignKey("operators.id", ondelete="CASCADE"), nullable=False
    )
    assigned_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("operators.id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.NEW, nullable=False
    )
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # лог выполнения
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Связи
    assignee: Mapped["Operator"] = relationship(
        back_populates="tasks_assigned", foreign_keys=[assigned_to]
    )
    creator: Mapped["Operator"] = relationship(
        back_populates="tasks_created", foreign_keys=[assigned_by]
    )
    candidate: Mapped[Optional["Candidate"]] = relationship(back_populates="tasks")

    @property
    def status_emoji(self) -> str:
        return {
            TaskStatus.NEW: "🆕",
            TaskStatus.IN_PROGRESS: "⏳",
            TaskStatus.DONE: "✅",
        }.get(self.status, "❓")

    def __repr__(self) -> str:
        return "<Task #{} {}>".format(self.id, self.title[:30])


class Category(Base):
    """Категория кандидатов (пользовательская)."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    emoji: Mapped[str] = mapped_column(String(10), default="📁", nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    candidates: Mapped[List["Candidate"]] = relationship(back_populates="category", lazy="selectin")

    def __repr__(self) -> str:
        return "<Category #{} {} {}>".format(self.id, self.emoji, self.name)
