"""
Контракт-61: Reply-клавиатуры (постоянные кнопки внизу).
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_reply_kb() -> ReplyKeyboardMarkup:
    """Постоянная клавиатура внизу экрана для быстрой навигации."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Кандидаты"), KeyboardButton(text="➕ Новый")],
            [KeyboardButton(text="📢 Реклама"), KeyboardButton(text="👥 Команда")],
            [KeyboardButton(text="📁 Категории"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🔍 Поиск"), KeyboardButton(text="🏠 Меню")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
