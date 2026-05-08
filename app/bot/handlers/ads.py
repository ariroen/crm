"""Контракт-61: Хендлер рекламы."""
import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.states.ad_fsm import AdFSM, AdBulkFSM
from app.services.ad_service import AdService

logger = logging.getLogger(__name__)
router = Router(name="ads")


def _fmt(ad):
    d = ad.post_date.strftime("%d.%m") if ad.post_date else "—"
    return "📢 *#{}* {} | {}₽ | {}кл | {}канд | CPL:{}\n🔗 {}".format(
        ad.id, ad.channel_name, int(ad.cost or 0), ad.clicks,
        ad.candidates_count, ad.cpl, ad.channel_link or "—")


def _list_kb(ads):
    b = [[InlineKeyboardButton(text="📢{} {}₽".format(a.channel_name[:18], int(a.cost or 0)),
          callback_data="ad:{}".format(a.id))] for a in ads]
    b.append([InlineKeyboardButton(text="➕ Добавить", callback_data="ad_add"),
              InlineKeyboardButton(text="📦 Массово", callback_data="ad_bulk")])
    b.append([InlineKeyboardButton(text="📊 Стат", callback_data="ad_stats"),
              InlineKeyboardButton(text="🔙 Меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=b)


def _card_kb(aid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👆+Клик", callback_data="adc:{}".format(aid)),
         InlineKeyboardButton(text="👤+Канд", callback_data="adk:{}".format(aid))],
        [InlineKeyboardButton(text="🗑Архив", callback_data="ada:{}".format(aid)),
         InlineKeyboardButton(text="🔙Список", callback_data="ads_list")]])


@router.message(Command("ads"))
async def cmd_ads(message: Message, session: AsyncSession):
    ads = await AdService(session).get_all()
    if not ads:
        await message.answer("📢 Нет записей.\n/ad\\_add — добавить\n/ad\\_bulk — массово", parse_mode="Markdown")
        return
    await message.answer("📢 *Реклама ({}):*".format(len(ads)), reply_markup=_list_kb(ads), parse_mode="Markdown")


@router.callback_query(F.data == "ads_list")
async def cb_list(cb: CallbackQuery, session: AsyncSession):
    ads = await AdService(session).get_all()
    await cb.message.edit_text("📢 *Реклама ({}):*".format(len(ads)), reply_markup=_list_kb(ads), parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data.startswith("ad:"))
async def cb_view(cb: CallbackQuery, session: AsyncSession):
    ad = await AdService(session).get_by_id(int(cb.data.split(":")[1]))
    if not ad: await cb.answer("❌"); return
    await cb.message.edit_text(_fmt(ad), reply_markup=_card_kb(ad.id), parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data.startswith("adc:"))
async def cb_click(cb: CallbackQuery, session: AsyncSession):
    svc = AdService(session); aid = int(cb.data.split(":")[1])
    ad = await svc.get_by_id(aid)
    if ad: await svc.update_clicks(aid, ad.clicks+1); ad = await svc.get_by_id(aid)
    await cb.message.edit_text(_fmt(ad), reply_markup=_card_kb(aid), parse_mode="Markdown")
    await cb.answer("👆+1")


@router.callback_query(F.data.startswith("adk:"))
async def cb_cand(cb: CallbackQuery, session: AsyncSession):
    svc = AdService(session); aid = int(cb.data.split(":")[1])
    ad = await svc.get_by_id(aid)
    if ad: await svc.update_candidates_count(aid, ad.candidates_count+1); ad = await svc.get_by_id(aid)
    await cb.message.edit_text(_fmt(ad), reply_markup=_card_kb(aid), parse_mode="Markdown")
    await cb.answer("👤+1")


@router.callback_query(F.data.startswith("ada:"))
async def cb_archive(cb: CallbackQuery, session: AsyncSession):
    svc = AdService(session); await svc.archive(int(cb.data.split(":")[1]))
    ads = await svc.get_all()
    await cb.message.edit_text("📢 *Реклама ({}):*".format(len(ads)), reply_markup=_list_kb(ads), parse_mode="Markdown")
    await cb.answer("🗑 Архив")


@router.callback_query(F.data == "ad_stats")
async def cb_stats(cb: CallbackQuery, session: AsyncSession):
    s = await AdService(session).stats_summary()
    t = "📊 *Статистика*\n📢{} | 💰{}₽ | 👆{} | 👤{}\nCPL:{:.0f}₽ CPC:{:.0f}₽".format(
        s["total_posts"], int(s["total_cost"]), s["total_clicks"], s["total_candidates"], s["avg_cpl"], s["avg_cpc"])
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="ads_list")]])
    await cb.message.edit_text(t, reply_markup=kb, parse_mode="Markdown"); await cb.answer()


# FSM: Добавить одну
@router.message(Command("ad_add"))
@router.callback_query(F.data == "ad_add")
async def fsm_start(event, state: FSMContext):
    m = event if isinstance(event, Message) else event.message
    await state.set_state(AdFSM.channel_name)
    await m.answer("📺 Введите *название канала*:", parse_mode="Markdown")
    if isinstance(event, CallbackQuery): await event.answer()


@router.message(AdFSM.channel_name)
async def fsm_name(message: Message, state: FSMContext):
    await state.update_data(channel_name=message.text.strip())
    await state.set_state(AdFSM.channel_link)
    await message.answer("🔗 Ссылка (или `-`):", parse_mode="Markdown")


@router.message(AdFSM.channel_link)
async def fsm_link(message: Message, state: FSMContext):
    link = message.text.strip() if message.text.strip() != "-" else None
    await state.update_data(channel_link=link)
    await state.set_state(AdFSM.cost)
    await message.answer("💰 Стоимость:")


@router.message(AdFSM.cost)
async def fsm_cost(message: Message, state: FSMContext, session: AsyncSession):
    try: cost = float(message.text.strip().replace(",", "."))
    except: cost = 0
    data = await state.get_data(); await state.clear()
    svc = AdService(session)
    ad = await svc.create(channel_name=data["channel_name"], channel_link=data.get("channel_link"),
                          cost=cost, post_date=datetime.now(), created_by=message.from_user.id)
    await message.answer(_fmt(ad), reply_markup=_card_kb(ad.id), parse_mode="Markdown")


# FSM: Массовый ввод
@router.message(Command("ad_bulk"))
@router.callback_query(F.data == "ad_bulk")
async def bulk_start(event, state: FSMContext):
    m = event if isinstance(event, Message) else event.message
    await state.set_state(AdBulkFSM.waiting_data)
    await m.answer("📦 Построчно: `Канал | ссылка | стоимость`", parse_mode="Markdown")
    if isinstance(event, CallbackQuery): await event.answer()


@router.message(AdBulkFSM.waiting_data)
async def bulk_data(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    items = []
    for line in message.text.strip().split("\n"):
        p = [x.strip() for x in line.split("|")]
        if not p[0]: continue
        it = {"channel_name": p[0], "post_date": datetime.now()}
        if len(p) >= 2 and p[1] != "-": it["channel_link"] = p[1]
        if len(p) >= 3:
            try: it["cost"] = float(p[2].replace(",", "."))
            except: pass
        items.append(it)
    if not items: await message.answer("⚠️ Нет данных"); return
    ads = await AdService(session).bulk_create(items, message.from_user.id)
    await message.answer("✅ Добавлено *{}* записей! /ads".format(len(ads)), parse_mode="Markdown")
