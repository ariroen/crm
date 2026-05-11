"""
Контракт-61: Инлайн-клавиатуры.
Карточка кандидата, главное меню, выбор источника, напоминания.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db.models import Candidate, TicketStatus, MedicalStatus, TrainingStatus


# ── Главное меню ──────────────────────────────────────────────


def main_menu_kb() -> InlineKeyboardMarkup:
    """Главное меню бота."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Список кандидатов", callback_data="list_candidates"),
    )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить кандидата", callback_data="add_candidate"),
        InlineKeyboardButton(text="🔍 Поиск", callback_data="search_candidate"),
    )
    builder.row(
        InlineKeyboardButton(text="📢 Реклама", callback_data="ads_list"),
        InlineKeyboardButton(text="👥 Команда", callback_data="ops_list"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
        InlineKeyboardButton(text="⏰ Напоминания", callback_data="my_reminders"),
    )
    builder.row(
        InlineKeyboardButton(text="🗄 Архив", callback_data="archive_list"),
    )
    return builder.as_markup()


# ── Карточка кандидата ────────────────────────────────────────

TICKET_LABELS = {
    TicketStatus.NEEDED: "🎫 Билет: Нужен",
    TicketStatus.BOUGHT: "🎫 Билет: Куплен 💰",
    TicketStatus.IN_TRANSIT: "🎫 Билет: В пути 🚂",
    TicketStatus.ARRIVED: "🎫 Билет: Прибыл ✅",
}

MEDICAL_LABELS = {
    MedicalStatus.NOT_STARTED: "🏥 Мед: Не начато",
    MedicalStatus.IN_PROGRESS: "🏥 Мед: В процессе ⏳",
    MedicalStatus.EXTRA_TESTS: "🏥 Мед: Доп. анализы 🔬",
    MedicalStatus.FIT: "🏥 Мед: Годен ✅",
    MedicalStatus.UNFIT: "🏥 Мед: Не годен ❌",
}

TRAINING_LABELS = {
    TrainingStatus.NONE: "🪖 Обучение: Не распределен",
    TrainingStatus.ASSIGNED: "🪖 Обучение: Распределен 📋",
    TrainingStatus.DEPARTED: "🪖 Обучение: Убыл ✅",
}


def candidate_card_kb(candidate: Candidate) -> InlineKeyboardMarkup:
    """Интерактивная карточка кандидата с кнопками-переключателями."""
    cid = candidate.id
    builder = InlineKeyboardBuilder()

    # Строка 1: Статусы (циклические переключатели)
    builder.row(
        InlineKeyboardButton(
            text=TICKET_LABELS.get(candidate.ticket_status, "🎫 Билет"),
            callback_data=f"cycle_ticket:{cid}",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=MEDICAL_LABELS.get(candidate.medical_status, "🏥 Мед"),
            callback_data=f"cycle_medical:{cid}",
        ),
    )
    builder.row(
    # Строка 3: ГИЦ и Билет
    builder.row(
        InlineKeyboardButton(text="🔎 ГИЦ: {}".format(candidate.gic_emoji), callback_data=f"toggle_gic:{cid}"),
        InlineKeyboardButton(text="🎫 Билет: {}".format(candidate.ticket_emoji), callback_data=f"cycle_ticket:{cid}"),
    )
    # Строка 4: Медицина и Оформление
    builder.row(
        InlineKeyboardButton(text="🏥 Мед: {}".format(candidate.medical_emoji), callback_data=f"cycle_medical:{cid}"),
        InlineKeyboardButton(text="📝 Оформл: {}".format(candidate.registration_emoji), callback_data=f"cycle_reg:{cid}"),
    )
    # Строка 5: Заметки, Фото, Категория
    builder.row(
        InlineKeyboardButton(text="📝 Заметки", callback_data=f"edit_notes:{cid}"),
        InlineKeyboardButton(text="📎 Фото", callback_data=f"add_photo_btn:{cid}"),
        InlineKeyboardButton(text="📁 Категория", callback_data=f"set_cat:{cid}"),
    )

    # Строка 6: Архив, PDF и Удалить
    builder.row(
        InlineKeyboardButton(text="📄 Экспорт PDF", callback_data=f"export_pdf:{cid}"),
        InlineKeyboardButton(text="🗄 В архив", callback_data=f"archive:{cid}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"confirm_delete:{cid}"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="list_candidates"),
    )

    return builder.as_markup()


# ── Список кандидатов ─────────────────────────────────────────


def candidates_list_kb(candidates: list[Candidate]) -> InlineKeyboardMarkup:
    """Список кандидатов с матрицей статусов."""
    builder = InlineKeyboardBuilder()
    for c in candidates[:20]:
        builder.row(
            InlineKeyboardButton(
                text=c.status_line,
                callback_data=f"view_candidate:{c.id}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить", callback_data="add_candidate"),
        InlineKeyboardButton(text="◀️ Меню", callback_data="main_menu"),
    )
    return builder.as_markup()


# ── Выбор источника ───────────────────────────────────────────


def source_choice_kb(candidate_id: int) -> InlineKeyboardMarkup:
    """Выбор рекламного источника при создании."""
    builder = InlineKeyboardBuilder()
    sources = [
        ("📺 Реклама 1", "Реклама 1"),
        ("📺 Реклама 2", "Реклама 2"),
        ("📺 Реклама 3", "Реклама 3"),
        ("🚪 Прямой вход", "Прямой вход"),
        ("📱 Сарафан", "Сарафанное радио"),
    ]
    for label, value in sources:
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"set_source:{candidate_id}:{value}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"view_candidate:{candidate_id}"),
    )
    return builder.as_markup()


# ── Пресеты напоминаний ──────────────────────────────────────


def reminder_presets_kb(candidate_id: int) -> InlineKeyboardMarkup:
    """Пресеты времени напоминания."""
    builder = InlineKeyboardBuilder()
    presets = [
        ("⏰ Через 2 часа", "2h"),
        ("🌅 Завтра утром (09:00)", "tomorrow_9"),
        ("🌆 Завтра днём (14:00)", "tomorrow_14"),
        ("📅 Через неделю", "1w"),
    ]
    for label, code in presets:
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"reminder_preset:{candidate_id}:{code}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"view_candidate:{candidate_id}"),
    )
    return builder.as_markup()


# ── Подтверждение ─────────────────────────────────────────────


def confirm_kb(action: str, target_id: int) -> InlineKeyboardMarkup:
    """Универсальная клавиатура подтверждения."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"confirm:{action}:{target_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"cancel:{action}:{target_id}"),
    )
    return builder.as_markup()

def delete_confirm_kb(candidate_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ ДА, УДАЛИТЬ", callback_data=f"delete_final:{candidate_id}"),
        InlineKeyboardButton(text="🔙 ОТМЕНА", callback_data=f"view_candidate:{candidate_id}"),
    )
    return builder.as_markup()
