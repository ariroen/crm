"""
Контракт-61: FSM-состояния для работы с кандидатами.
"""

from aiogram.fsm.state import State, StatesGroup


class CandidateFSM(StatesGroup):
    """Состояния при ручном добавлении кандидата."""
    waiting_fast_entry = State()      # Ожидание строки "ФИО Телефон Канал"
    waiting_photo = State()           # Ожидание скриншота билета
    waiting_source_choice = State()   # Ожидание выбора источника
    waiting_search_query = State()    # Ожидание поискового запроса


class ReminderFSM(StatesGroup):
    """Состояния при ручной установке напоминания."""
    waiting_time_choice = State()     # Ожидание выбора пресета времени
    waiting_custom_time = State()     # Ожидание ввода произвольного времени


class NotesFSM(StatesGroup):
    """Состояния для заметок."""
    waiting_note_text = State()       # Ожидание текста заметки
