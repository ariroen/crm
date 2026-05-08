"""
Контракт-61: Сборка бота — экземпляр Bot, Dispatcher, регистрация роутеров.
"""
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.bot.middlewares.db_middleware import DbSessionMiddleware

from app.bot.handlers.start import router as start_router
from app.bot.handlers.candidate import router as candidate_router
from app.bot.handlers.voice import router as voice_router
from app.bot.handlers.photo import router as photo_router
from app.bot.handlers.reminders import router as reminders_router
from app.bot.handlers.ads import router as ads_router
from app.bot.handlers.operators import router as operators_router
from app.bot.handlers.backup import router as backup_router
from app.bot.callbacks.candidate_cb import router as candidate_cb_router

logger = logging.getLogger(__name__)


def create_bot() -> Bot:
    """Создать экземпляр бота с прокси (если указан)."""
    session = None
    if settings.PROXY_URL:
        session = AiohttpSession(proxy=settings.PROXY_URL)
        logger.info("🌐 Прокси для Telegram API: %s", settings.PROXY_URL.split("@")[-1])

    return Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
        session=session,
    )


def create_dispatcher() -> Dispatcher:
    """Создать диспетчер с роутерами и middleware."""
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware для БД-сессий
    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())

    # Регистрация роутеров (порядок важен! Сначала callback'и кандидатов)
    dp.include_routers(
        start_router,
        backup_router,
        candidate_cb_router,  # ВАЖНО: Должен быть перед candidate_router для обработки callback'ов
        candidate_router,
        voice_router,
        photo_router,
        reminders_router,
        ads_router,
        operators_router,
    )

    logger.info("🤖 Dispatcher создан, роутеры зарегистрированы")
    return dp
