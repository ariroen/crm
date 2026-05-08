"""
Контракт-61: Фоновые задачи — рапорты, уведомления, дедлайны.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Candidate, Task, TaskStatus, AdPost
from app.db.session import async_session_maker

logger = logging.getLogger(__name__)


async def daily_report(bot, chat_id: int):
    """Дневной рапорт в 21:00 — сводка за сутки."""
    async with async_session_maker() as session:
        yesterday = datetime.now() - timedelta(hours=24)

        # Кандидаты
        result = await session.execute(
            select(Candidate).where(Candidate.archived == False)
        )
        all_c = list(result.scalars().all())
        new_today = [c for c in all_c if c.created_at >= yesterday]

        from app.db.models import TicketStatus, MedicalStatus, TrainingStatus
        bought = sum(1 for c in all_c if c.ticket_status == TicketStatus.BOUGHT)
        arrived = sum(1 for c in all_c if c.ticket_status == TicketStatus.ARRIVED)
        fit = sum(1 for c in all_c if c.medical_status == MedicalStatus.FIT)
        departed = sum(1 for c in all_c if c.training_status == TrainingStatus.DEPARTED)

        # Задачи
        result = await session.execute(
            select(Task).where(Task.status != TaskStatus.DONE)
        )
        active_tasks = list(result.scalars().all())

        # Реклама
        result = await session.execute(select(AdPost))
        ads = list(result.scalars().all())
        total_cost = sum(a.cost for a in ads)
        total_leads = sum(a.leads_count for a in ads)

        lines = [
            "📊 ДНЕВНОЙ РАПОРТ",
            "━━━━━━━━━━━━━━━━━━━━━",
            "📅 {}".format(datetime.now().strftime("%d.%m.%Y")),
            "",
            "👥 КАНДИДАТЫ:",
            "  Всего: {}".format(len(all_c)),
            "  Новых за 24ч: {}".format(len(new_today)),
            "  Билет куплен: {}".format(bought),
            "  Прибыли: {}".format(arrived),
            "  Годен: {}".format(fit),
            "  Убыли: {}".format(departed),
            "",
            "📋 ЗАДАЧИ: {} активных".format(len(active_tasks)),
        ]

        overdue = [t for t in active_tasks if t.deadline and t.deadline < datetime.now()]
        if overdue:
            lines.append("  ⚠️ Просроченных: {}".format(len(overdue)))
            for t in overdue[:3]:
                lines.append("    • #{} {}".format(t.id, t.title[:30]))

        if ads:
            cpl = round(total_cost / total_leads) if total_leads else 0
            lines.extend([
                "",
                "📢 РЕКЛАМА:",
                "  Каналов: {}".format(len(ads)),
                "  Расход: {}₽".format(total_cost),
                "  Лидов: {}".format(total_leads),
                "  CPL: {}₽".format(cpl),
            ])

        conv = round(departed / len(all_c) * 100) if all_c else 0
        lines.extend(["", "📈 Конверсия: {}%".format(conv)])

        report = "\n".join(lines)
        try:
            await bot.send_message(chat_id, report)
            logger.info("📊 Дневной рапорт отправлен")
        except Exception as e:
            logger.error("❌ Ошибка отправки рапорта: %s", e)


async def check_stale_candidates(bot, chat_id: int, hours=48):
    """Уведомление о зависших — если кандидат не обновлялся >48ч."""
    async with async_session_maker() as session:
        threshold = datetime.now() - timedelta(hours=hours)
        result = await session.execute(
            select(Candidate).where(
                Candidate.archived == False,
                Candidate.updated_at < threshold,
            ).order_by(Candidate.updated_at)
        )
        stale = list(result.scalars().all())

        if not stale:
            return

        lines = ["⚠️ ЗАВИСШИЕ КАНДИДАТЫ ({})".format(len(stale)),
                 "━━━━━━━━━━━━━━━━━━━━━",
                 "Без обновлений более {}ч:".format(hours), ""]

        from app.db.models import TicketStatus, MedicalStatus
        for c in stale[:15]:
            days = (datetime.now() - c.updated_at).days
            stage = ""
            if c.ticket_status == TicketStatus.NEEDED:
                stage = "❌ билет не куплен"
            elif c.ticket_status == TicketStatus.BOUGHT:
                stage = "🎫 ждёт отправки"
            elif c.medical_status == MedicalStatus.IN_PROGRESS:
                stage = "🏥 на медицине"
            elif c.medical_status == MedicalStatus.NOT_STARTED:
                stage = "🏥 медицина не начата"
            else:
                stage = "{} {}".format(c.ticket_emoji, c.medical_emoji)
            lines.append("  • {} — {}д — {}".format(c.full_name, days, stage))

        try:
            await bot.send_message(chat_id, "\n".join(lines))
            logger.info("⚠️ Уведомление о %d зависших", len(stale))
        except Exception as e:
            logger.error("❌ Ошибка уведомления: %s", e)


async def check_task_deadlines(bot, chat_id: int):
    """Уведомление о задачах с истекающим дедлайном (в ближайший час)."""
    async with async_session_maker() as session:
        now = datetime.now()
        soon = now + timedelta(hours=1)
        result = await session.execute(
            select(Task).where(
                Task.status != TaskStatus.DONE,
                Task.deadline != None,
                Task.deadline <= soon,
                Task.deadline >= now,
            )
        )
        urgent = list(result.scalars().all())
        if not urgent:
            return

        lines = ["🔔 ДЕДЛАЙНЫ ЗАДАЧ (ближайший час):", ""]
        for t in urgent:
            dl = t.deadline.strftime("%H:%M")
            lines.append("  {} #{} {} — до {}".format(t.status_emoji, t.id, t.title[:30], dl))

        try:
            await bot.send_message(chat_id, "\n".join(lines))
        except Exception as e:
            logger.error("❌ %s", e)
