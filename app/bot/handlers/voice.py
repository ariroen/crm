"""
Контракт-61: Обработка голосовых сообщений.
Whisper транскрибация → LLM анализ → авто-действие.
"""
import io
import logging
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.candidate import format_card
from app.bot.keyboards.inline import candidate_card_kb, main_menu_kb
from app.services.groq_service import groq_service
from app.services.candidate_service import CandidateService
from app.services.reminder_service import ReminderService

logger = logging.getLogger(__name__)
router = Router(name="voice")


@router.message(F.voice)
async def handle_voice(message: Message, session: AsyncSession, bot: Bot):
    """Обработка голосового сообщения: транскрибация + AI-анализ."""
    wait_msg = await message.answer("🎤 Обрабатываю голосовое...")

    try:
        # 1. Скачиваем аудио — используем bot.download() для совместимости с прокси
        voice = message.voice
        buf = io.BytesIO()
        await bot.download(voice, destination=buf)
        buf.seek(0)
        audio_bytes = buf.read()

        logger.info("🎤 Скачано аудио: %d байт, duration=%ds", len(audio_bytes), voice.duration or 0)

        if len(audio_bytes) < 100:
            await wait_msg.edit_text("⚠️ Аудиофайл слишком маленький. Попробуйте записать длиннее.")
            return

        # 2. Транскрибация через Whisper
        text = await groq_service.transcribe(audio_bytes, filename="voice.ogg")
        logger.info("🎤 Транскрибация результат: '%s' (len=%d)", text[:100] if text else "EMPTY", len(text or ""))

        if not text or not text.strip():
            await wait_msg.edit_text("⚠️ Не удалось распознать речь. Попробуйте говорить громче и чётче.")
            return

        await wait_msg.edit_text("🎤 Распознано: {}\n\n🧠 Анализирую...".format(text))

        # 3. AI-анализ намерения
        result = await groq_service.analyze_intent(text, user_id=message.from_user.id)
        intent = result.get("intent", "unknown")
        data = result.get("data", {})
        summary = result.get("summary", "")

        # 4. Выполняем действие
        svc = CandidateService(session)

        if intent in ("create_candidate", "update_candidate", "update_ticket", "update_medical", "update_training", "search", "list"):
            msg_text, candidate = await svc.process_ai_data(intent, data, message.from_user.id)

            if candidate:
                candidate = await svc.get_by_id(candidate.id)
                reply = "🧠 {}\n\n{}\n\n{}".format(summary, msg_text, format_card(candidate))
                await wait_msg.edit_text(reply, reply_markup=candidate_card_kb(candidate))
            else:
                await wait_msg.edit_text(
                    "🧠 {}\n\n{}".format(summary, msg_text),
                    reply_markup=main_menu_kb(),
                )

        elif intent == "set_reminder":
            reminder_text = data.get("reminder_text", text)
            reminder_dt_str = data.get("reminder_datetime")
            candidate_name = data.get("full_name")

            remind_at = None
            if reminder_dt_str:
                try:
                    remind_at = datetime.strptime(reminder_dt_str, "%Y-%m-%d %H:%M")
                except ValueError:
                    pass
            if not remind_at:
                remind_at = datetime.now() + timedelta(hours=2)

            candidate_id = None
            if candidate_name:
                candidates = await svc.search(candidate_name)
                if candidates:
                    candidate_id = candidates[0].id

            rsvc = ReminderService(session)
            await rsvc.create(
                user_id=message.from_user.id,
                remind_at=remind_at,
                message=reminder_text,
                candidate_id=candidate_id,
            )
            await wait_msg.edit_text(
                "🧠 {}\n\n⏰ Напоминание на {}\n📝 {}".format(
                    summary, remind_at.strftime('%d.%m.%Y %H:%M'), reminder_text),
                reply_markup=main_menu_kb(),
            )
        else:
            await wait_msg.edit_text(
                "🎤 Распознано: {}\n\n⚠️ Не удалось определить команду.\nПереформулируйте.".format(text),
                reply_markup=main_menu_kb(),
            )

    except Exception as e:
        logger.exception("Ошибка обработки голосового: %s", e)
        try:
            await wait_msg.edit_text("❌ Ошибка: {}".format(str(e)[:200]))
        except Exception:
            pass
