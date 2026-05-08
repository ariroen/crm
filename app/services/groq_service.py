"""
Контракт-61: Groq AI Service.

Два основных метода:
  1. transcribe()     — Whisper large-v3: голос → текст
  2. analyze_intent() — Llama 3.3 70B: текст → структурированный JSON

Включает retry с exponential backoff при ошибках API.
"""

import asyncio
import json
import logging
from datetime import datetime

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [1, 3, 7]  # секунды между попытками


MEGA_PROMPT = """Ты — военный диспетчер-аналитик системы "Контракт-61".
Твоя задача — анализировать текстовые команды оператора и извлекать структурированные данные.

ОБЯЗАТЕЛЬНО верни ответ СТРОГО в формате JSON. Никакого текста вне JSON.

Формат ответа:
{{
  "intent": "<один из: create_candidate | update_candidate | update_ticket | update_medical | update_training | set_reminder | search | list | unknown>",
  "data": {{
    "full_name": "ФИО или имя (если указано) — формат: Фамилия И. или Фамилия",
    "phone": "телефон (только цифры, если указан)",
    "source": "источник прихода (если указан)",
    "ticket_status": "needed | bought | in_transit | arrived (если речь о билете)",
    "arrival_date": "YYYY-MM-DD (если указана дата прибытия)",
    "medical_status": "not_started | in_progress | extra_tests | fit | unfit (если речь о медицине)",
    "training_status": "none | assigned | departed (если речь об обучении)",
    "reminder_text": "текст напоминания (если нужно)",
    "reminder_datetime": "YYYY-MM-DD HH:MM (если указано время напоминания)",
    "notes": "доп. заметки"
  }},
  "summary": "Краткий рапорт в военном стиле (1 предложение)"
}}

ПРАВИЛА:
1. Неупомянутые поля — null.
2. Телефоны: "восемь девятьсот" = "8900", "восемь-девять-ноль-ноль" = "8900". Собирай цифры.
3. Имена: "Фамилия Имя" → "Фамилия И.", только фамилия → "Фамилия".
4. "С рекламы" → source = "Реклама". "С канала Новости" → source = "Реклама: Новости".
5. "Билет купили / взяли билет" → ticket_status = "bought".
6. "Прошел врачей / годен / всё ок" → medical_status = "fit".
7. "Не годен / списан / отказ" → medical_status = "unfit".
8. "Напомни завтра в 10" → парси дату относительно текущей.
9. "Запиши нового" / "Добавь" → intent = "create_candidate".
10. "Найди / Покажи" → intent = "search".
11. "Список / Все кандидаты" → intent = "list".
12. Текущая дата и время: {current_datetime}
13. Отвечай ТОЛЬКО JSON. Никакого текста до или после."""


class GroqService:
    """Сервис интеграции с Groq API (Whisper + Llama 3.3)."""

    BASE_URL = "https://api.groq.com/openai/v1"
    MAX_CONTEXT = 5  # последних сообщений в памяти

    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self._proxy = settings.PROXY_URL if settings.PROXY_URL else None
        self._context: dict[int, list[str]] = {}  # user_id → [messages]

    def add_context(self, user_id: int, text: str):
        """Добавить сообщение в контекст пользователя."""
        if user_id not in self._context:
            self._context[user_id] = []
        self._context[user_id].append(text)
        if len(self._context[user_id]) > self.MAX_CONTEXT:
            self._context[user_id] = self._context[user_id][-self.MAX_CONTEXT:]

    def get_context(self, user_id: int) -> str:
        """Получить контекст пользователя."""
        msgs = self._context.get(user_id, [])
        if not msgs:
            return ""
        return "Предыдущие сообщения оператора:\n" + "\n".join(
            "{}. {}".format(i+1, m) for i, m in enumerate(msgs)
        )

    def _get_client(self, timeout=30.0):
        return httpx.AsyncClient(proxy=self._proxy, timeout=timeout)

    async def _retry(self, func, *args, **kwargs):
        """Обёртка retry с exponential backoff."""
        last_err = None
        for attempt in range(MAX_RETRIES):
            try:
                return await func(*args, **kwargs)
            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout) as e:
                last_err = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.warning(
                        "⚠️ Groq API ошибка (попытка %d/%d): %s. Повтор через %dс...",
                        attempt + 1, MAX_RETRIES, str(e)[:100], delay,
                    )
                    await asyncio.sleep(delay)
        logger.error("❌ Groq API: все %d попыток исчерпаны", MAX_RETRIES)
        raise last_err

    async def _do_transcribe(self, audio_data, filename):
        logger.info("🎤 Отправка в Groq: %d байт, файл=%s", len(audio_data), filename)
        async with self._get_client(timeout=60.0) as client:
            response = await client.post(
                "%s/audio/transcriptions" % self.BASE_URL,
                headers={"Authorization": "Bearer %s" % self.api_key},
                files={"file": (filename, audio_data, "audio/ogg")},
                data={
                    "model": "whisper-large-v3-turbo",
                    "language": "ru",
                    "response_format": "verbose_json",
                },
            )
            logger.info("🎤 Groq HTTP %d, body len=%d", response.status_code, len(response.content))
            response.raise_for_status()
            body = response.json()
            logger.info("🎤 Groq ответ ключи: %s", list(body.keys()))
            text = body.get("text", "")
            if not text:
                # Попробовать другие поля
                text = body.get("transcription", body.get("result", ""))
                logger.warning("🎤 Поле 'text' пустое, пробуем другие: '%s'", text[:100] if text else "EMPTY")
            logger.info("🎤 Транскрибация: '%s'", text[:200] if text else "EMPTY")
            return text

    async def _do_analyze(self, text, context=""):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        prompt = MEGA_PROMPT.format(current_datetime=now)
        if context:
            prompt += "\n\n" + context
        async with self._get_client(timeout=30.0) as client:
            response = await client.post(
                "%s/chat/completions" % self.BASE_URL,
                headers={
                    "Authorization": "Bearer %s" % self.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1024,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            result = json.loads(content)
            logger.info("🧠 Intent: %s | Summary: %s", result.get("intent"), result.get("summary"))
            return result

    async def transcribe(self, audio_data, filename="voice.ogg"):
        """Транскрибация с retry."""
        return await self._retry(self._do_transcribe, audio_data, filename)

    async def analyze_intent(self, text, user_id=None):
        """Анализ намерения с retry и контекстом."""
        context = ""
        if user_id:
            context = self.get_context(user_id)
            self.add_context(user_id, text)
        return await self._retry(self._do_analyze, text, context)

    async def health_check(self):
        try:
            async with self._get_client(timeout=10.0) as client:
                response = await client.get(
                    "%s/models" % self.BASE_URL,
                    headers={"Authorization": "Bearer %s" % self.api_key},
                )
                return response.status_code == 200
        except Exception:
            return False


groq_service = GroqService()
