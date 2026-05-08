import os
import shutil
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.filters import Command
from app.bot.keyboards.inline import main_menu_kb
from app.bot.keyboards.backup import backup_kb, restore_confirm_kb

backup_router = Router()

BACKUP_DIR = "/app/backups"
DB_PATH = "/app/data/contract61.db"

# Убеждаемся, что папка существует
os.makedirs(BACKUP_DIR, exist_ok=True)

@backup_router.message(Command("backup"))
async def cmd_backup(message: Message):
    """Ручной запуск создания бэкапа по команде"""
    await create_backup(message)

@backup_router.callback_query(F.data == "backup_create")
async def cb_backup_create(callback: CallbackQuery):
    await callback.answer()
    await create_backup(callback.message)

@backup_router.callback_query(F.data == "backup_restore_list")
async def cb_backup_restore_list(callback: CallbackQuery):
    await callback.answer()
    files = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".db")]
    if not files:
        await callback.message.edit_text("📂 Папка бэкапов пуста.\nСначала создайте резервную копию.", reply_markup=main_menu_kb())
        return
    
    # Сортируем по дате изменения (новые сверху)
    files.sort(key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)), reverse=True)
    
    text = "📂 Доступные бэкапы:\n\n"
    keyboard = []
    for i, f in enumerate(files[:10]): # Показываем последние 10
        size = os.path.getsize(os.path.join(BACKUP_DIR, f)) / 1024
        text += f"{i+1}. <code>{f}</code> ({size:.1f} KB)\n"
        keyboard.append([{"text": f"🔄 {f}", "callback_data": f"backup_restore_{f}"}])
    keyboard.append([{"text": "🔙 Назад", "callback_data": "backup_menu"}])
    
    await callback.message.edit_text(text, reply_markup=inline_keyboard(keyboard), parse_mode="HTML")

@backup_router.callback_query(F.data.startswith("backup_restore_"))
async def cb_backup_restore_confirm(callback: CallbackQuery):
    filename = callback.data.split("backup_restore_")[1]
    filepath = os.path.join(BACKUP_DIR, filename)
    
    if not os.path.exists(filepath):
        await callback.answer("❌ Файл не найден!", show_alert=True)
        return

    text = f"⚠️ <b>Внимание!</b>\nВы собираетесь восстановить базу данных из файла:\n<code>{filename}</code>\n\nВсе текущие данные будут <b>перезаписаны</b>!\nПродолжить?"
    await callback.message.edit_text(text, reply_markup=restore_confirm_kb(filename), parse_mode="HTML")

@backup_router.callback_query(F.data.startswith("backup_restore_confirm_"))
async def cb_backup_restore_execute(callback: CallbackQuery):
    filename = callback.data.split("backup_restore_confirm_")[1]
    filepath = os.path.join(BACKUP_DIR, filename)
    
    await callback.answer("⏳ Восстановление...")
    
    try:
        current_db_path = DB_PATH
        
        # Создаем бэкап текущей базы перед восстановлением на всякий случай
        auto_backup_name = f"auto_backup_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        if os.path.exists(current_db_path):
            shutil.copy2(current_db_path, os.path.join(BACKUP_DIR, auto_backup_name))
        
        # Копируем файл бэкапа поверх текущей базы
        shutil.copy2(filepath, current_db_path)
        
        await callback.message.edit_text(f"✅ <b>Восстановление успешно!</b>\nБаза заменена на {filename}.\nРекомендуется перезапустить бота для применения изменений.", parse_mode="HTML", reply_markup=main_menu_kb())
        
        # Тут можно добавить логику перезагрузки, если нужно, но обычно достаточно рестарта контейнера пользователем
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка при восстановлении: {e}", reply_markup=main_menu_kb())

@backup_router.callback_query(F.data == "backup_menu")
async def cb_backup_menu(callback: CallbackQuery):
    await callback.answer()
    text = "💾 <b>Управление бэкапами</b>\n\nЗдесь вы можете создать резервную копию базы данных или восстановить её из ранее сохраненной копии."
    await callback.message.edit_text(text, reply_markup=backup_kb(), parse_mode="HTML")

async def create_backup(message: Message):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{timestamp}.db"
        filepath = os.path.join(BACKUP_DIR, filename)
        
        current_db_path = DB_PATH
            
        if not os.path.exists(current_db_path):
            await message.answer("❌ Файл базы данных не найден!", reply_markup=main_menu_kb())
            return

        shutil.copy2(current_db_path, filepath)
        size = os.path.getsize(filepath) / 1024
        
        await message.answer(
            f"✅ <b>Бэкап создан!</b>\nФайл: <code>{filename}</code>\nРазмер: {size:.1f} KB\nСохранено в: {BACKUP_DIR}",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка создания бэкапа: {e}", reply_markup=main_menu_kb())

# Вспомогательная функция для клавиатуры
def inline_keyboard(buttons):
    return InlineKeyboardMarkup(inline_keyboard=buttons)
