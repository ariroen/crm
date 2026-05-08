"""
Контракт-61: Хэндлеры кандидатов — CRUD, быстрый ввод, списки.
"""
import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import (
    candidate_card_kb, candidates_list_kb, main_menu_kb, source_choice_kb,
)
from app.bot.states.candidate_fsm import CandidateFSM
from app.services.candidate_service import CandidateService
from app.db.models import TicketStatus, MedicalStatus, TrainingStatus

router = Router(name="candidate")


def format_card(c) -> str:
    lines = [
        "🪖 Карточка #{}".format(c.id),
        "━━━━━━━━━━━━━━━━━━━━━",
        "👤 {}".format(c.full_name),
    ]
    if c.phone:
        lines.append("📞 {}".format(c.phone))
    if c.source:
        lines.append("📺 Источник: {}".format(c.source))
    if hasattr(c, 'category') and c.category:
        lines.append("📁 {}".format(c.category.name))
    if hasattr(c, 'operator') and c.operator:
        lines.append("👤 Оператор: {}".format(c.operator.name))
    lines.append("")
    lines.append("  {}  Билет".format(c.ticket_emoji))
    if c.arrival_date:
        lines.append("  📅 Прибытие: {}".format(c.arrival_date.strftime('%d.%m.%Y')))
    lines.append("  {}  Медицина".format(c.medical_emoji))
    lines.append("  {}  Обучение".format(c.training_emoji))
    if c.notes:
        lines.append("\n📝 {}".format(c.notes[-200:]))
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🕐 {}".format(c.created_at.strftime('%d.%m.%Y %H:%M')))
    return "\n".join(lines)


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    await state.set_state(CandidateFSM.waiting_fast_entry)
    await message.answer(
        "✏️ **Быстрое добавление**\n\n"
        "Введите: `ФИО Телефон Источник`\n"
        "Пример: `Петров 89991234567 Реклама_ТГ`",
        parse_mode="Markdown",
    )


@router.message(CandidateFSM.waiting_fast_entry)
async def process_fast_entry(message: Message, state: FSMContext, session: AsyncSession):
    text = message.text.strip() if message.text else ""
    if not text:
        await message.answer("⚠️ Пустая строка.")
        return

    phone_match = re.search(r'(\+?[78]\d{9,10})', text)
    phone, source = None, None
    if phone_match:
        phone = phone_match.group(1)
        parts = text.split(phone)
        name = parts[0].strip()
        source = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
    else:
        tokens = text.split()
        name = " ".join(tokens[:3]) if len(tokens) > 3 else " ".join(tokens)
        source = " ".join(tokens[3:]) if len(tokens) > 3 else None

    if not name:
        await message.answer("⚠️ Не определено имя.")
        return

    await state.clear()
    svc = CandidateService(session)
    c = await svc.create(full_name=name, created_by=message.from_user.id, phone=phone, source=source)

    if not source:
        await message.answer(
            format_card(c) + "\n\n📺 **Выберите источник:**",
            reply_markup=source_choice_kb(c.id), parse_mode="Markdown",
        )
    else:
        await message.answer(format_card(c), reply_markup=candidate_card_kb(c), parse_mode="Markdown")


@router.message(Command("list"))
async def cmd_list(message: Message, session: AsyncSession):
    svc = CandidateService(session)
    candidates = await svc.list_active()
    if not candidates:
        await message.answer("📋 Список пуст.", reply_markup=main_menu_kb())
        return
    await message.answer(
        f"📋 **Кандидаты ({len(candidates)}):**",
        reply_markup=candidates_list_kb(candidates), parse_mode="Markdown",
    )


@router.callback_query(F.data == "list_candidates")
async def cb_list(callback: CallbackQuery, session: AsyncSession):
    svc = CandidateService(session)
    candidates = await svc.list_active()
    try:
        if not candidates:
            await callback.message.edit_text("📋 Список пуст.", reply_markup=main_menu_kb())
        else:
            await callback.message.edit_text(
                f"📋 **Кандидаты ({len(candidates)}):**",
                reply_markup=candidates_list_kb(candidates), parse_mode="Markdown",
            )
    except Exception as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise
    await callback.answer()


@router.callback_query(F.data == "add_candidate")
async def cb_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CandidateFSM.waiting_fast_entry)
    try:
        await callback.message.edit_text(
            "✏️ **Быстрое добавление**\nВведите: `ФИО Телефон Источник`\nИли 🎤 голосовое",
            parse_mode="Markdown",
        )
    except Exception as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise
    await callback.answer()


@router.callback_query(F.data.startswith("view_candidate:"))
async def cb_view(callback: CallbackQuery, session: AsyncSession):
    cid = int(callback.data.split(":")[1])
    svc = CandidateService(session)
    c = await svc.get_by_id(cid)
    if not c:
        await callback.answer("⚠️ Не найден", show_alert=True)
        return
    try:
        await callback.message.edit_text(
            format_card(c), reply_markup=candidate_card_kb(c), parse_mode="Markdown",
        )
    except Exception as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise
    await callback.answer()


@router.callback_query(F.data == "search_candidate")
async def cb_search_start(callback: CallbackQuery, state: FSMContext):
    await state.set_data({"search_mode": True})
    try:
        await callback.message.edit_text("🔍 Введите имя или телефон:", parse_mode="Markdown")
    except Exception as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise
    await callback.answer()


@router.callback_query(F.data == "stats")
async def cb_stats(callback: CallbackQuery, session: AsyncSession):
    svc = CandidateService(session)
    all_c = await svc.list_active()
    total = len(all_c)
    t_need = sum(1 for c in all_c if c.ticket_status == TicketStatus.NEEDED)
    t_buy = sum(1 for c in all_c if c.ticket_status == TicketStatus.BOUGHT)
    t_arr = sum(1 for c in all_c if c.ticket_status == TicketStatus.ARRIVED)
    m_fit = sum(1 for c in all_c if c.medical_status == MedicalStatus.FIT)
    m_unf = sum(1 for c in all_c if c.medical_status == MedicalStatus.UNFIT)
    tr_dep = sum(1 for c in all_c if c.training_status == TrainingStatus.DEPARTED)
    conv = round(tr_dep / total * 100) if total else 0
    text = (
        f"📊 **СТАТИСТИКА**\n━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего: **{total}**\n\n"
        f"🎫 Нужен: {t_need} | Куплен: {t_buy} | Прибыл: {t_arr}\n"
        f"🏥 Годен: {m_fit} | Не годен: {m_unf}\n"
        f"🪖 Убыло: {tr_dep}\n"
        f"📈 Конверсия: {conv}%"
    )
    try:
        await callback.message.edit_text(text, reply_markup=main_menu_kb(), parse_mode="Markdown")
    except Exception as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise
    await callback.answer()
