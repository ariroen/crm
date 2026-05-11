"""
Контракт-61: Управление сессиями БД.
Асинхронный движок SQLAlchemy + автосоздание таблиц.
"""

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.base import Base


# Создаём папку data если не существует
_db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
if _db_path.startswith("./"):
    _db_path_obj = Path(_db_path)
    _db_path_obj.parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """Получить сессию БД."""
    async with async_session() as session:
        yield session


async def init_db() -> None:
    """Создать все таблицы при старте."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
