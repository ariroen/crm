"""
Контракт-61: Диспетчер — Точка входа.
Запускает Telegram-бота, планировщик напоминаний и FastAPI.
"""
import asyncio
import logging
import sys
from datetime import datetime, timedelta

import uvicorn

from app.config import settings
from app.db.session import init_db, async_session
from app.bot.bot import create_bot, create_dispatcher
from app.services.reminder_service import ReminderService

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("contract61")


async def reminder_loop(bot):
    """Фоновая задача: проверка и отправка напоминаний каждые 30 сек."""
    logger.info("⏰ Планировщик напоминаний запущен")
    while True:
        try:
            async with async_session() as session:
                svc = ReminderService(session)
                pending = await svc.get_pending()
                for reminder in pending:
                    try:
                        text = f"⏰ **НАПОМИНАНИЕ**\n\n📝 {reminder.message}"
                        if reminder.candidate_id:
                            text += f"\n👤 Кандидат #{reminder.candidate_id}"
                        await bot.send_message(chat_id=reminder.user_id, text=text, parse_mode="Markdown")
                        await svc.mark_sent(reminder.id)
                        logger.info("⏰ Напоминание #%d отправлено", reminder.id)
                    except Exception as e:
                        logger.error("⏰ Ошибка отправки напоминания #%d: %s", reminder.id, e)
        except Exception as e:
            logger.error("⏰ Ошибка в цикле напоминаний: %s", e)
        await asyncio.sleep(30)


async def backup_loop():
    """Фоновая задача: бэкап БД каждые 6 часов."""
    import shutil
    from pathlib import Path

    db_path = Path(settings.DATABASE_URL.replace("sqlite+aiosqlite:///", ""))
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    interval = 6 * 3600  # 6 часов

    logger.info("💾 Авто-бэкап запущен (каждые 6ч → %s)", backup_dir)
    while True:
        await asyncio.sleep(interval)
        try:
            if db_path.exists():
                ts = datetime.now().strftime("%Y%m%d_%H%M")
                dest = backup_dir / f"contract61_{ts}.db"
                shutil.copy2(str(db_path), str(dest))
                logger.info("💾 Бэкап создан: %s", dest.name)

                # Удалить бэкапы старше 7 дней
                import time
                cutoff = time.time() - 7 * 86400
                for f in backup_dir.glob("contract61_*.db"):
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
                        logger.info("🗑 Старый бэкап удалён: %s", f.name)
        except Exception as e:
            logger.error("💾 Ошибка бэкапа: %s", e)


async def run_api():
    """Запустить FastAPI в фоне."""
    from app.api.routes import app as fastapi_app
    config = uvicorn.Config(
        fastapi_app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """Главная точка входа."""
    logger.info("=" * 50)
    logger.info("🪖 КОНТРАКТ-61: ДИСПЕТЧЕР")
    logger.info("=" * 50)

    # 1. Инициализация БД
    await init_db()
    logger.info("✅ База данных инициализирована")

    # 2. Создание бота
    bot = create_bot()
    dp = create_dispatcher()
    logger.info("✅ Бот создан")

    # 3. Запуск фоновых задач
    reminder_task = asyncio.create_task(reminder_loop(bot))
    api_task = asyncio.create_task(run_api())
    backup_task = asyncio.create_task(backup_loop())

    # Рапорты и уведомления
    from app.services.scheduler import daily_report, check_stale_candidates, check_task_deadlines
    admin_id = settings.admin_ids[0] if settings.admin_ids else None

    async def report_loop():
        """Дневной рапорт в 21:00."""
        while True:
            now = datetime.now()
            target = now.replace(hour=21, minute=0, second=0)
            if target <= now:
                target += timedelta(days=1)
            wait = (target - now).total_seconds()
            logger.info("📊 Рапорт через %.0f мин", wait / 60)
            await asyncio.sleep(wait)
            if admin_id:
                await daily_report(bot, admin_id)

    async def stale_loop():
        """Проверка зависших каждые 12ч."""
        await asyncio.sleep(60)  # подождать старта
        while True:
            if admin_id:
                await check_stale_candidates(bot, admin_id)
            await asyncio.sleep(12 * 3600)

    async def deadline_loop():
        """Проверка дедлайнов каждые 30 мин."""
        await asyncio.sleep(120)
        while True:
            if admin_id:
                await check_task_deadlines(bot, admin_id)
            await asyncio.sleep(30 * 60)

    report_task = asyncio.create_task(report_loop())
    stale_task = asyncio.create_task(stale_loop())
    deadline_task = asyncio.create_task(deadline_loop())

    logger.info("✅ Планировщик, API, бэкапы, рапорты запущены")

    # 4. Запуск polling
    logger.info("🚀 Бот запущен! Ожидание сообщений...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        for t in [reminder_task, api_task, backup_task, report_task, stale_task, deadline_task]:
            t.cancel()
        await bot.session.close()
        logger.info("🛑 Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Остановка по Ctrl+C")
