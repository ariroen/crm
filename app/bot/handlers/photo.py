"""
Контракт-61: Обработка фото (скриншоты билетов, чеков).
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import candidate_card_kb
from app.bot.states.candidate_fsm import CandidateFSM
from app.bot.handlers.candidate import format_card
from app.services.candidate_service import CandidateService

logger = logging.getLogger(__name__)
router = Router(name="photo")


@router.callback_query(F.data.startswith("attach_photo:"))
async def cb_attach_photo(callback: CallbackQuery, state: FSMContext):
    """Начать прикрепление фото к кандидату."""
    cid = int(callback.data.split(":")[1])
    await state.set_state(CandidateFSM.waiting_photo)
    await state.update_data(photo_candidate_id=cid)
    await callback.message.edit_text(
        "📎 **Отправьте фото** (скриншот билета или чек).\n"
        "Фото будет привязано к карточке кандидата.",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(CandidateFSM.waiting_photo, F.photo)
async def process_photo(message: Message, state: FSMContext, session: AsyncSession):
    """Сохранить фото к кандидату."""
    data = await state.get_data()
    cid = data.get("photo_candidate_id")
    if not cid:
        await message.answer("⚠️ Ошибка: кандидат не выбран.")
        await state.clear()
        return

    file_id = message.photo[-1].file_id  # Лучшее качество
    svc = CandidateService(session)
    await svc.add_photo(candidate_id=cid, file_id=file_id, file_type="ticket")
    await state.clear()

    candidate = await svc.get_by_id(cid)
    if candidate:
        await message.answer(
            f"✅ Фото прикреплено!\n\n{format_card(candidate)}",
            reply_markup=candidate_card_kb(candidate), parse_mode="Markdown",
        )
    else:
        await message.answer("✅ Фото сохранено.")


@router.callback_query(F.data.startswith("view_photos:"))
async def cb_view_photos(callback: CallbackQuery, session: AsyncSession):
    """Показать все фото кандидата."""
    cid = int(callback.data.split(":")[1])
    svc = CandidateService(session)
    photos = await svc.get_photos(cid)

    if not photos:
        await callback.answer("🖼 Фото не найдены", show_alert=True)
        return

    candidate = await svc.get_by_id(cid)
    await callback.answer(f"🖼 Отправляю {len(photos)} фото...")

    from aiogram import Bot
    bot: Bot = callback.bot
    for photo in photos[:10]:
        caption = f"📎 {photo.file_type} | {photo.created_at.strftime('%d.%m.%Y %H:%M')}"
        if photo.description:
            caption += f"\n📝 {photo.description}"
        await bot.send_photo(
            chat_id=callback.message.chat.id,
            photo=photo.file_id,
            caption=caption,
        )
