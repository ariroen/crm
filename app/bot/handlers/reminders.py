"""
Контракт-61: Хэндлеры напоминаний.
"""
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import reminder_presets_kb, main_menu_kb
from app.services.reminder_service import ReminderService

router = Router(name="reminders")


@router.callback_query(F.data.startswith("set_reminder:"))
async def cb_set_reminder(callback: CallbackQuery):
    """Показать пресеты напоминаний."""
    cid = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "⏰ **Выберите время напоминания:**",
        reply_markup=reminder_presets_kb(cid), parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reminder_preset:"))
async def cb_reminder_preset(callback: CallbackQuery, session: AsyncSession):
    """Установить напоминание по пресету."""
    parts = callback.data.split(":")
    cid = int(parts[1])
    preset = parts[2]

    now = datetime.now()
    presets = {
        "2h": (now + timedelta(hours=2), "Через 2 часа"),
        "tomorrow_9": (now.replace(hour=9, minute=0, second=0) + timedelta(days=1), "Завтра в 09:00"),
        "tomorrow_14": (now.replace(hour=14, minute=0, second=0) + timedelta(days=1), "Завтра в 14:00"),
        "1w": (now + timedelta(weeks=1), "Через неделю"),
    }
    remind_at, label = presets.get(preset, (now + timedelta(hours=2), "Через 2 часа"))

    rsvc = ReminderService(session)
    await rsvc.create(
        user_id=callback.from_user.id,
        remind_at=remind_at,
        message=f"Проверить кандидата #{cid}",
        candidate_id=cid,
    )
    await callback.message.edit_text(
        f"✅ Напоминание установлено: **{label}**\n"
        f"📅 {remind_at.strftime('%d.%m.%Y %H:%M')}",
        reply_markup=main_menu_kb(), parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "my_reminders")
async def cb_my_reminders(callback: CallbackQuery, session: AsyncSession):
    """Список активных напоминаний."""
    rsvc = ReminderService(session)
    reminders = await rsvc.get_user_reminders(callback.from_user.id)
    if not reminders:
        await callback.message.edit_text(
            "⏰ Активных напоминаний нет.", reply_markup=main_menu_kb(),
        )
        await callback.answer()
        return

    lines = []
    for r in reminders[:15]:
        cand = f" (Кандидат #{r.candidate_id})" if r.candidate_id else ""
        lines.append(f"• {r.remind_at.strftime('%d.%m %H:%M')} — {r.message}{cand}")

    await callback.message.edit_text(
        f"⏰ **Напоминания ({len(reminders)}):**\n\n" + "\n".join(lines),
        reply_markup=main_menu_kb(), parse_mode="Markdown",
    )
    await callback.answer()
