"""
Контракт-61: Хэндлер /start, главное меню и навигация по кнопкам.
"""
import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import main_menu_kb, candidates_list_kb
from app.bot.keyboards.reply import main_reply_kb
from app.services.candidate_service import CandidateService
from app.services.ad_service import AdService
from app.services.operator_service import OperatorService

logger = logging.getLogger(__name__)
router = Router(name="start")

WELCOME = """
🪖 **КОНТРАКТ-61: ДИСПЕТЧЕР**
━━━━━━━━━━━━━━━━━━━━━
Система учёта кандидатов.

🎤 Голосовой ввод — диктуй, ИИ запишет
➕ Добавление кандидатов
📢 Учёт рекламы и каналов
👥 Управление командой и задачами
⏰ Напоминания

Используй кнопки внизу ↓
━━━━━━━━━━━━━━━━━━━━━
"""


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(WELCOME, reply_markup=main_reply_kb(), parse_mode="Markdown")
    await message.answer("🪖 **Главное меню:**", reply_markup=main_menu_kb(), parse_mode="Markdown")


@router.message(Command("menu"))
@router.message(F.text == "🏠 Меню")
async def cmd_menu(message: Message):
    await message.answer("🪖 **Главное меню:**", reply_markup=main_menu_kb(), parse_mode="Markdown")


@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """
🪖 **СПРАВКА**

**Кнопки внизу:**
📋 Кандидаты — список всех
➕ Новый — добавить кандидата
📢 Реклама — управление рекламой
👥 Команда — операторы и задачи
📊 Статистика — сводка
⏰ Напоминания — мои напоминания
🔍 Поиск — найти кандидата

**Голосовые команды:**
_\"Запиши Иванова, телефон 89001234567\"_
_\"Иванову купили билет на завтра\"_
_\"Напомни проверить Петрова завтра\"_

**Команды:**
/ads — реклама
/team — команда
/ad\\_add — добавить рекламу
/ad\\_bulk — массовый ввод рекламы
/add\\_operator — добавить оператора
/assign — закрепить кандидата
"""
    await message.answer(help_text, parse_mode="Markdown")


# ── Reply-кнопки навигации ──

@router.message(F.text == "📋 Кандидаты")
async def btn_candidates(message: Message, session: AsyncSession):
    svc = CandidateService(session)
    candidates = await svc.get_all()
    if not candidates:
        await message.answer("📋 Нет кандидатов. Добавьте первого!", reply_markup=main_menu_kb())
        return
    await message.answer(
        "📋 **Кандидаты ({})**:".format(len(candidates)),
        reply_markup=candidates_list_kb(candidates), parse_mode="Markdown")


@router.message(F.text == "➕ Новый")
async def btn_add(message: Message):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Ввести данные", callback_data="add_candidate")],
        [InlineKeyboardButton(text="🎤 Голосом", callback_data="voice_hint")],
        [InlineKeyboardButton(text="🔙 Меню", callback_data="main_menu")],
    ])
    await message.answer("➕ **Добавить кандидата:**", reply_markup=kb, parse_mode="Markdown")


@router.message(F.text == "📢 Реклама")
async def btn_ads(message: Message, session: AsyncSession):
    svc = AdService(session)
    ads = await svc.get_all()
    from app.bot.handlers.ads import _list_kb
    if not ads:
        await message.answer("📢 Нет записей.\nНажмите ➕ чтобы добавить.", reply_markup=main_menu_kb())
        return
    await message.answer("📢 **Реклама ({})**:".format(len(ads)), reply_markup=_list_kb(ads), parse_mode="Markdown")


@router.message(F.text == "👥 Команда")
async def btn_team(message: Message, session: AsyncSession):
    svc = OperatorService(session)
    ops = await svc.get_all()
    from app.bot.handlers.operators import _team_kb
    if not ops:
        await message.answer("👥 Нет операторов. /add_operator — добавить")
        return
    await message.answer("👥 Команда ({}):".format(len(ops)), reply_markup=_team_kb(ops))


@router.message(F.text == "📊 Статистика")
async def btn_stats(message: Message, session: AsyncSession):
    svc = CandidateService(session)
    stats = await svc.get_stats()
    ad_svc = AdService(session)
    ad_stats = await ad_svc.stats_summary()
    text = (
        "📊 **СВОДКА**\n\n"
        "👤 Кандидатов: {total}\n"
        "🎫 Билет куплен: {bought}\n"
        "🚂 В пути: {transit}\n"
        "✅ Прибыли: {arrived}\n"
        "🏥 Годен: {fit}\n"
        "🪖 Убыл: {departed}\n\n"
        "📢 **Реклама:**\n"
        "💰 Расход: {ad_cost}₽\n"
        "👆 Клики: {ad_clicks}\n"
        "👤 Привлечено: {ad_cands}"
    ).format(
        ad_cost=int(ad_stats["total_cost"]),
        ad_clicks=ad_stats["total_clicks"],
        ad_cands=ad_stats["total_candidates"],
        **stats,
    )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Детали рекламы", callback_data="ad_stats")],
        [InlineKeyboardButton(text="🔙 Меню", callback_data="main_menu")],
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.message(F.text == "⏰ Напоминания")
async def btn_reminders(message: Message, session: AsyncSession):
    from app.services.reminder_service import ReminderService
    svc = ReminderService(session)
    reminders = await svc.get_active(message.from_user.id)
    if not reminders:
        await message.answer("⏰ Нет активных напоминаний.", reply_markup=main_menu_kb())
        return
    lines = ["⏰ **Напоминания:**\n"]
    for r in reminders[:10]:
        dt = r.remind_at.strftime("%d.%m %H:%M")
        lines.append("• {} — {}".format(dt, r.message[:50]))
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Меню", callback_data="main_menu")]])
    await message.answer("\n".join(lines), reply_markup=kb, parse_mode="Markdown")


@router.message(F.text == "📁 Категории")
async def btn_cats(message: Message, session: AsyncSession):
    from sqlalchemy import select
    from app.db.models import Category
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    result = await session.execute(select(Category).order_by(Category.name))
    cats = list(result.scalars().all())
    b = [[InlineKeyboardButton(text="{} {} ({})".format(c.emoji, c.name, len(c.candidates)),
          callback_data="cat:{}".format(c.id))] for c in cats]
    b.append([InlineKeyboardButton(text="➕ Новая категория", callback_data="cat_add")])
    b.append([InlineKeyboardButton(text="🔙 Меню", callback_data="main_menu")])
    await message.answer("📁 Категории:", reply_markup=InlineKeyboardMarkup(inline_keyboard=b))


@router.message(F.text == "🔍 Поиск")
async def btn_search(message: Message):
    await message.answer("🔍 Введите ФИО или часть имени для поиска:")


# ── Inline callbacks ──

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    await callback.message.edit_text("🪖 **Главное меню:**", reply_markup=main_menu_kb(), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "voice_hint")
async def cb_voice_hint(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎤 **Отправьте голосовое сообщение!**\n\n"
        "Примеры:\n"
        "• _\"Запиши Иванова, телефон 89001234567\"_\n"
        "• _\"Петров прошёл медкомиссию, годен\"_\n"
        "• _\"Купили билет Сидорову на завтра\"_",
        parse_mode="Markdown",
    )
    await callback.answer()
