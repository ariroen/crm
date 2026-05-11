"""
Контракт-61: Callback-хэндлеры для циклического переключения статусов.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.candidate import format_card
from app.bot.keyboards.inline import candidate_card_kb, main_menu_kb, delete_confirm_kb
from app.bot.states.candidate_fsm import NotesFSM
from app.services.candidate_service import CandidateService
from app.services.pdf_service import pdf_service
from aiogram.types import BufferedInputFile

router = Router(name="candidate_callbacks")


@router.callback_query(F.data.startswith("export_pdf:"))
async def cb_export_pdf(callback: CallbackQuery, session: AsyncSession):
    cid = int(callback.data.split(":")[1])
    svc = CandidateService(session)
    c = await svc.get_by_id(cid)
    if not c:
        await callback.answer("⚠️ Не найден", show_alert=True)
        return
    
    await callback.answer("⏳ Генерация PDF...")
    pdf_bytes = pdf_service.generate_candidate_card(c)
    
    filename = f"Candidate_{c.id}_{c.full_name.replace(' ', '_')}.pdf"
    file = BufferedInputFile(pdf_bytes, filename=filename)
    
    await callback.message.answer_document(
        document=file,
        caption=f"📄 Анкета кандидата: <b>{c.full_name}</b>",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("cycle_ticket:"))
async def cb_cycle_ticket(callback: CallbackQuery, session: AsyncSession):
    cid = int(callback.data.split(":")[1])
    svc = CandidateService(session)
    c = await svc.cycle_ticket_status(cid)
    if not c:
        await callback.answer("⚠️ Не найден", show_alert=True)
        return
    # Если статус стал "Куплен" — предложить прикрепить фото
    from app.db.models import TicketStatus
    if c.ticket_status == TicketStatus.BOUGHT:
        await callback.answer("🎫 Куплен! Прикрепите скрин билета кнопкой 📎")
    else:
        await callback.answer(f"🎫 → {c.ticket_emoji}")
    await callback.message.edit_text(
        format_card(c), reply_markup=candidate_card_kb(c), parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cycle_medical:"))
async def cb_cycle_medical(callback: CallbackQuery, session: AsyncSession):
    cid = int(callback.data.split(":")[1])
    svc = CandidateService(session)
    c = await svc.cycle_medical_status(cid)
    if not c:
        await callback.answer("⚠️ Не найден", show_alert=True)
        return
    await callback.answer(f"🏥 → {c.medical_emoji}")
    await callback.message.edit_text(
        format_card(c), reply_markup=candidate_card_kb(c), parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("toggle_gic:"))
async def cb_toggle_gic(callback: CallbackQuery, session: AsyncSession):
    cid = int(callback.data.split(":")[1])
    svc = CandidateService(session)
    c = await svc.toggle_gic_status(cid)
    if not c:
        await callback.answer("⚠️ Не найден", show_alert=True)
        return
    status = "В ГИЦ ✅" if c.gic_status else "НЕ В ГИЦ ❌"
    await callback.answer(f"🔎 ГИЦ: {status}")
    await callback.message.edit_text(
        format_card(c), reply_markup=candidate_card_kb(c), parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cycle_reg:"))
async def cb_cycle_reg(callback: CallbackQuery, session: AsyncSession):
    cid = int(callback.data.split(":")[1])
    svc = CandidateService(session)
    c = await svc.cycle_registration_status(cid)
    if not c:
        await callback.answer("⚠️ Не найден", show_alert=True)
        return
    await callback.answer(f"📝 Оформление → {c.registration_emoji}")
    await callback.message.edit_text(
        format_card(c), reply_markup=candidate_card_kb(c), parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("set_source:"))
async def cb_set_source(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":", 2)
    cid = int(parts[1])
    source = parts[2]
    svc = CandidateService(session)
    c = await svc.get_by_id(cid)
    if not c:
        await callback.answer("⚠️ Не найден", show_alert=True)
        return
    c.source = source
    await session.commit()
    await session.refresh(c)
    await callback.answer(f"📺 Источник: {source}")
    await callback.message.edit_text(
        format_card(c), reply_markup=candidate_card_kb(c), parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("archive:"))
async def cb_archive(callback: CallbackQuery, session: AsyncSession):
    cid = int(callback.data.split(":")[1])
    svc = CandidateService(session)
    c = await svc.archive(cid)
    if c:
        from aiogram.utils.markdown import html_decoration as hd
        await callback.message.edit_text(
            f"🗄 <b>{hd.quote(c.full_name)}</b> отправлен в архив.", reply_markup=main_menu_kb(), parse_mode="HTML",
        )
        await callback.answer("🗄 В архив!")
    else:
        await callback.answer("⚠️ Не найден", show_alert=True)


@router.callback_query(F.data.startswith("edit_notes:"))
async def cb_edit_notes(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    cid = int(callback.data.split(":")[1])
    svc = CandidateService(session)
    c = await svc.get_by_id(cid)
    if not c:
        await callback.answer("⚠️ Не найден", show_alert=True)
        return

    # Показать текущие заметки
    current = c.notes or "Пусто"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Добавить заметку", callback_data="note_add:{}".format(cid))],
        [InlineKeyboardButton(text="🗑 Очистить все", callback_data="note_clear:{}".format(cid))],
        [InlineKeyboardButton(text="🔙 К карточке", callback_data="view_candidate:{}".format(cid))],
    ])
    await callback.message.edit_text(
        "📝 Заметки — {}\n━━━━━━━━━━━━━━━\n{}".format(c.full_name, current),
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("note_add:"))
async def cb_note_add(callback: CallbackQuery, state: FSMContext):
    cid = int(callback.data.split(":")[1])
    await state.update_data(note_candidate_id=cid)
    await state.set_state(NotesFSM.waiting_note_text)
    await callback.message.answer("📝 Введите текст заметки для кандидата:")
    await callback.answer()


@router.message(NotesFSM.waiting_note_text)
async def msg_note_text(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    cid = data.get("note_candidate_id")
    if not cid:
        await message.answer("⚠️ Ошибка: кандидат не определён.")
        return

    svc = CandidateService(session)
    c = await svc.get_by_id(cid)
    if not c:
        await message.answer("⚠️ Кандидат не найден.")
        return

    # Добавляем заметку с датой/временем
    from datetime import datetime
    timestamp = datetime.now().strftime("%d.%m %H:%M")
    new_note = "[{}] {}".format(timestamp, message.text.strip())

    if c.notes:
        c.notes = c.notes + "\n" + new_note
    else:
        c.notes = new_note

    await session.commit()
    await session.refresh(c)

    await message.answer(
        "✅ Заметка добавлена к {}\n\n📝 {}".format(c.full_name, new_note),
        reply_markup=candidate_card_kb(c),
    )


@router.callback_query(F.data.startswith("note_clear:"))
async def cb_note_clear(callback: CallbackQuery, session: AsyncSession):
    cid = int(callback.data.split(":")[1])
    svc = CandidateService(session)
    c = await svc.get_by_id(cid)
    if c:
        c.notes = None
        await session.commit()
        await session.refresh(c)
        await callback.answer("🗑 Заметки очищены")
        await callback.message.edit_text(
            format_card(c), reply_markup=candidate_card_kb(c), parse_mode="HTML",
        )
    else:
        await callback.answer("⚠️ Не найден", show_alert=True)


@router.callback_query(F.data == "archive_list")
async def cb_archive_list(callback: CallbackQuery, session: AsyncSession):
    from sqlalchemy import select
    from app.db.models import Candidate
    result = await session.execute(
        select(Candidate).where(Candidate.archived == True).order_by(Candidate.updated_at.desc()).limit(20)
    )
    archived = list(result.scalars().all())
    if not archived:
        await callback.message.edit_text("🗄 Архив пуст.", reply_markup=main_menu_kb())
    else:
        lines = [f"• {c.full_name} ({c.updated_at.strftime('%d.%m.%Y')})" for c in archived]
        await callback.message.edit_text(
            f"🗄 <b>Архив ({len(archived)}):</b>\n\n" + "\n".join(lines),
            reply_markup=main_menu_kb(), parse_mode="HTML",
        )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete:"))
async def cb_confirm_delete(callback: CallbackQuery):
    cid = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "⚠️ **ВЫ УВЕРЕНЫ?**\nУдаление кандидата нельзя отменить.",
        reply_markup=delete_confirm_kb(cid),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_final:"))
async def cb_delete_final(callback: CallbackQuery, session: AsyncSession):
    cid = int(callback.data.split(":")[1])
    svc = CandidateService(session)
    success = await svc.delete(cid)
    if success:
        await callback.message.edit_text("🗑 Кандидат успешно удален.", reply_markup=main_menu_kb())
        await callback.answer("🗑 Удалено")
    else:
        await callback.answer("⚠️ Ошибка при удалении", show_alert=True)
