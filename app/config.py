from __future__ import annotations

"""
Контракт-61: Центральная конфигурация.
Все настройки загружаются из .env файла.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Настройки приложения."""

    # Telegram
    BOT_TOKEN: str = ""
    ADMIN_IDS: str = ""  # comma-separated

    # Groq AI
    GROQ_API_KEY: str = ""

    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR}/data/contract61.db"

    # Proxy
    PROXY_URL: str = ""

    # FastAPI
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8080

    # Timezone
    TZ: str = "Europe/Moscow"

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def admin_ids(self) -> list[int]:
        """Список ID администраторов."""
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]


settings = Settings()
