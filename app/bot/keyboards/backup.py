from aiogram.types import InlineKeyboardMarkup

def backup_kb():
    """Клавиатура меню бэкапов"""
    keyboard = [
        [{"text": "💾 Создать бэкап", "callback_data": "backup_create"}],
        [{"text": "📂 Восстановить из бэкапа", "callback_data": "backup_restore_list"}],
        [{"text": "🔙 В главное меню", "callback_data": "main_menu"}]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def restore_confirm_kb(filename):
    """Клавиатура подтверждения восстановления"""
    keyboard = [
        [{"text": f"✅ Да, восстановить {filename}", "callback_data": f"backup_restore_confirm_{filename}"}],
        [{"text": "❌ Отмена", "callback_data": "backup_menu"}]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
