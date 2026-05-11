"""
Контракт-61: FSM-состояния для рекламы и операторов.
"""
from aiogram.fsm.state import State, StatesGroup


class AdFSM(StatesGroup):
    """Пошаговый ввод рекламного поста."""
    channel_name = State()
    channel_link = State()
    post_link = State()
    cost = State()
    post_date = State()


class AdBulkFSM(StatesGroup):
    """Массовый ввод каналов."""
    waiting_data = State()


class OperatorFSM(StatesGroup):
    """Добавление оператора."""
    waiting_forward = State()
    waiting_name = State()


class TaskFSM(StatesGroup):
    """Создание задачи."""
    select_operator = State()
    title = State()
    description = State()
    deadline = State()
