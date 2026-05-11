"""
Контракт-61: Middleware для инъекции сессии БД в каждый хэндлер.
"""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.db.session import async_session


class DbSessionMiddleware(BaseMiddleware):
    """
    Создаёт AsyncSession и передаёт её в data['session'].
    Сессия автоматически закрывается после обработки.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with async_session() as session:
            data["session"] = session
            return await handler(event, data)
