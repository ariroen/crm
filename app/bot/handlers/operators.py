"""Контракт-61: Хендлер команды, задач и категорий."""
import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup as IKM, InlineKeyboardButton as IKB
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.operator_service import OperatorService
from app.db.models import OperatorRole, TaskStatus, Category, Candidate

logger = logging.getLogger(__name__)
router = Router(name="operators")


# ── FSM States ──
class OpFSM(StatesGroup):
    wait_forward = State()
    wait_name = State()

class TaskFSM(StatesGroup):
    title = State()
    description = State()
    pick_candidate = State()

class TaskCommentFSM(StatesGroup):
    text = State()

class CatFSM(StatesGroup):
    name = State()
    emoji = State()

class AssignCatFSM(StatesGroup):
    pick_cat = State()


# ── Навигация команды ──

def _team_kb(ops):
    b = [[IKB(text="{} {} | {} канд".format(o.role_emoji, o.name, len(o.candidates)),
          callback_data="op:{}".format(o.id))] for o in ops]
    b.append([IKB(text="➕ Оператор", callback_data="op_add"),
              IKB(text="📋 Все задачи", callback_data="all_tasks")])
    b.append([IKB(text="📁 Категории", callback_data="cats_list"),
              IKB(text="🔙 Меню", callback_data="main_menu")])
    return IKM(inline_keyboard=b)


@router.message(Command("team"))
async def cmd_team(message: Message, session: AsyncSession):
    ops = await OperatorService(session).get_all()
    if not ops:
        await message.answer("👥 Нет операторов.\nНажмите ➕ чтобы добавить.")
        return
    await message.answer("👥 Команда ({}):".format(len(ops)), reply_markup=_team_kb(ops))


@router.callback_query(F.data == "ops_list")
async def cb_ops(cb: CallbackQuery, session: AsyncSession):
    ops = await OperatorService(session).get_all()
    if not ops:
        await cb.message.edit_text("👥 Нет операторов.")
        return
    await cb.message.edit_text("👥 Команда ({}):".format(len(ops)), reply_markup=_team_kb(ops))
    await cb.answer()


# ── Карточка оператора ──

@router.callback_query(F.data.startswith("op:"))
async def cb_op(cb: CallbackQuery, session: AsyncSession):
    svc = OperatorService(session)
    op = await svc.get_by_id(int(cb.data.split(":")[1]))
    if not op:
        await cb.answer("❌"); return
    cands = await svc.get_operator_candidates(op.id)
    tasks = await svc.get_tasks_for_operator(op.id)
    active_tasks = [t for t in tasks if t.status != TaskStatus.DONE]

    lines = ["{} {} (ID:{})".format(op.role_emoji, op.name, op.user_id),
             "━━━━━━━━━━━━━━━",
             "👤 Кандидатов: {}".format(len(cands)),
             "📋 Задач активных: {}".format(len(active_tasks))]
    if cands:
        lines.append("\nЗакреплённые:")
        for c in cands[:10]:
            lines.append("  • {} {}".format(c.full_name, c.ticket_emoji))
    if active_tasks:
        lines.append("\nЗадачи:")
        for t in active_tasks[:5]:
            dl = " ⏰{}".format(t.deadline.strftime("%d.%m")) if t.deadline else ""
            lines.append("  {} #{} {}{}".format(t.status_emoji, t.id, t.title[:30], dl))

    kb = IKM(inline_keyboard=[
        [IKB(text="📋 Все задачи", callback_data="op_tasks:{}".format(op.id)),
         IKB(text="👤 Кандидаты", callback_data="op_cands:{}".format(op.id))],
        [IKB(text="📝 Новая задача", callback_data="task_new:{}".format(op.id))],
        [IKB(text="🔙 Команда", callback_data="ops_list")]])
    await cb.message.edit_text("\n".join(lines), reply_markup=kb)
    await cb.answer()


# ── Кандидаты оператора ──

@router.callback_query(F.data.startswith("op_cands:"))
async def cb_cands(cb: CallbackQuery, session: AsyncSession):
    svc = OperatorService(session)
    op_id = int(cb.data.split(":")[1])
    cands = await svc.get_operator_candidates(op_id)
    if not cands:
        await cb.answer("Нет кандидатов", show_alert=True); return
    b = [[IKB(text="{} {} {}".format(c.full_name[:20], c.ticket_emoji, c.medical_emoji),
          callback_data="view_candidate:{}".format(c.id))] for c in cands[:15]]
    b.append([IKB(text="🔙", callback_data="op:{}".format(op_id))])
    await cb.message.edit_text("👤 Кандидаты оператора:", reply_markup=IKM(inline_keyboard=b))
    await cb.answer()


# ── Задачи оператора ──

@router.callback_query(F.data.startswith("op_tasks:"))
async def cb_tasks(cb: CallbackQuery, session: AsyncSession):
    svc = OperatorService(session)
    op_id = int(cb.data.split(":")[1])
    tasks = await svc.get_tasks_for_operator(op_id, include_done=True)
    if not tasks:
        await cb.answer("Нет задач", show_alert=True); return
    b = []
    for t in tasks[:10]:
        dl = " ⏰{}".format(t.deadline.strftime("%d.%m")) if t.deadline else ""
        b.append([IKB(text="{} {}{}".format(t.status_emoji, t.title[:30], dl),
                  callback_data="task:{}".format(t.id))])
    b.append([IKB(text="📝 Новая", callback_data="task_new:{}".format(op_id)),
              IKB(text="🔙", callback_data="op:{}".format(op_id))])
    await cb.message.edit_text("📋 Задачи:", reply_markup=IKM(inline_keyboard=b))
    await cb.answer()


# ── Все задачи ──

@router.callback_query(F.data == "all_tasks")
async def cb_all_tasks(cb: CallbackQuery, session: AsyncSession):
    svc = OperatorService(session)
    tasks = await svc.get_tasks_with_deadlines()
    # Добавить все не-выполненные
    from sqlalchemy import select as sel
    from app.db.models import Task
    result = await session.execute(sel(Task).where(Task.status != TaskStatus.DONE).order_by(Task.created_at.desc()).limit(20))
    all_t = list(result.scalars().all())
    if not all_t:
        await cb.answer("Нет задач", show_alert=True); return
    b = []
    for t in all_t:
        dl = " ⏰{}".format(t.deadline.strftime("%d.%m")) if t.deadline else ""
        b.append([IKB(text="{} #{} {}{}".format(t.status_emoji, t.id, t.title[:25], dl),
                  callback_data="task:{}".format(t.id))])
    b.append([IKB(text="🔙 Команда", callback_data="ops_list")])
    await cb.message.edit_text("📋 Все активные задачи:", reply_markup=IKM(inline_keyboard=b))
    await cb.answer()


# ── Карточка задачи ──

@router.callback_query(F.data.startswith("task:"))
async def cb_task(cb: CallbackQuery, session: AsyncSession):
    from app.db.models import Task
    tid = int(cb.data.split(":")[1])
    task = await session.get(Task, tid)
    if not task:
        await cb.answer("❌"); return
    dl = task.deadline.strftime("%d.%m.%Y %H:%M") if task.deadline else "—"
    cand_name = task.candidate.full_name if task.candidate else "—"
    lines = ["{} Задача #{}".format(task.status_emoji, task.id),
             "━━━━━━━━━━━━━━━",
             "📌 {}".format(task.title),
             "📝 {}".format(task.description or "—"),
             "👤 Кандидат: {}".format(cand_name),
             "⏰ Дедлайн: {}".format(dl),
             "📊 Статус: {}".format(task.status.value)]
    if task.history:
        lines.append("\n📜 История:\n{}".format(task.history[-500:]))
    b = []
    if task.status == TaskStatus.NEW:
        b.append([IKB(text="▶️ Взять в работу", callback_data="ts:{}:in_progress".format(tid))])
    if task.status == TaskStatus.IN_PROGRESS:
        b.append([IKB(text="✅ Выполнено", callback_data="ts:{}:done".format(tid))])
    b.append([IKB(text="💬 Комментарий", callback_data="task_comment:{}".format(tid))])
    b.append([IKB(text="🔙 Назад", callback_data="ops_list")])
    await cb.message.edit_text("\n".join(lines), reply_markup=IKM(inline_keyboard=b))
    await cb.answer()


@router.callback_query(F.data.startswith("ts:"))
async def cb_ts(cb: CallbackQuery, session: AsyncSession):
    parts = cb.data.split(":")
    tid, new_status = int(parts[1]), TaskStatus(parts[2])
    svc = OperatorService(session)
    from app.db.models import Task
    task = await session.get(Task, tid)
    if task:
        ts = datetime.now().strftime("%d.%m %H:%M")
        entry = "[{}] {} → {}".format(ts, task.status.value, new_status.value)
        task.history = (task.history + "\n" + entry) if task.history else entry
        task.status = new_status
        await session.commit()
    await cb.answer("✅ #{} → {}".format(tid, new_status.value))


# ── Комментарий к задаче ──

@router.callback_query(F.data.startswith("task_comment:"))
async def cb_comment(cb: CallbackQuery, state: FSMContext):
    tid = int(cb.data.split(":")[1])
    await state.update_data(comment_task_id=tid)
    await state.set_state(TaskCommentFSM.text)
    await cb.message.answer("💬 Введите комментарий к задаче #{}:".format(tid))
    await cb.answer()


@router.message(TaskCommentFSM.text)
async def msg_comment(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data(); await state.clear()
    tid = data["comment_task_id"]
    from app.db.models import Task
    task = await session.get(Task, tid)
    if not task:
        await message.answer("❌ Задача не найдена"); return
    ts = datetime.now().strftime("%d.%m %H:%M")
    entry = "[{}] 💬 {}".format(ts, message.text.strip())
    task.history = (task.history + "\n" + entry) if task.history else entry
    await session.commit()
    await message.answer("✅ Комментарий к задаче #{} добавлен".format(tid))


# ── Создание задачи ──

@router.callback_query(F.data.startswith("task_new:"))
async def task_start(cb: CallbackQuery, state: FSMContext):
    op_id = int(cb.data.split(":")[1])
    await state.update_data(assigned_to=op_id)
    await state.set_state(TaskFSM.title)
    await cb.message.answer("📝 Заголовок задачи:")
    await cb.answer()


@router.message(TaskFSM.title)
async def task_title(message: Message, state: FSMContext):
    await state.update_data(task_title=message.text.strip())
    await state.set_state(TaskFSM.description)
    await message.answer("📝 Описание (или `-` пропустить):")


@router.message(TaskFSM.description)
async def task_desc(message: Message, state: FSMContext, session: AsyncSession):
    desc = message.text.strip() if message.text.strip() != "-" else None
    data = await state.get_data(); await state.clear()
    svc = OperatorService(session)
    creator = await svc.get_by_user_id(message.from_user.id)
    creator_id = creator.id if creator else data["assigned_to"]
    task = await svc.create_task(
        assigned_to=data["assigned_to"], assigned_by=creator_id,
        title=data["task_title"], description=desc)
    await message.answer("✅ Задача #{} создана: {}".format(task.id, task.title))


# ── Добавление оператора ──

@router.message(Command("add_operator"))
@router.callback_query(F.data == "op_add")
async def op_start(event, state: FSMContext):
    m = event if isinstance(event, Message) else event.message
    await state.set_state(OpFSM.wait_forward)
    await m.answer("👤 Перешлите сообщение от оператора или введите его Telegram ID:")
    if isinstance(event, CallbackQuery): await event.answer()


@router.message(OpFSM.wait_forward)
async def op_id(message: Message, state: FSMContext):
    uid = None
    if message.forward_from:
        uid = message.forward_from.id
        await state.update_data(user_id=uid, suggested=message.forward_from.full_name)
    else:
        try: uid = int(message.text.strip())
        except: pass
    if not uid:
        await message.answer("⚠️ Не определить ID"); return
    await state.update_data(user_id=uid)
    await state.set_state(OpFSM.wait_name)
    data = await state.get_data()
    s = data.get("suggested", "")
    await message.answer("📝 Имя оператора{}:".format(" ({})".format(s) if s else ""))


@router.message(OpFSM.wait_name)
async def op_name(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data(); await state.clear()
    svc = OperatorService(session)
    existing = await svc.get_by_user_id(data["user_id"])
    if existing:
        await message.answer("⚠️ Уже оператор: {}".format(existing.name)); return
    op = await svc.add_operator(data["user_id"], message.text.strip())
    await message.answer("✅ Оператор {} добавлен (ID:{})".format(op.name, op.user_id))


# ── Закрепление кандидата за оператором ──

@router.callback_query(F.data.startswith("assign_op:"))
async def cb_assign(cb: CallbackQuery, session: AsyncSession):
    """callback: assign_op:candidate_id"""
    cid = int(cb.data.split(":")[1])
    ops = await OperatorService(session).get_all()
    if not ops:
        await cb.answer("Нет операторов", show_alert=True); return
    b = [[IKB(text="{} {}".format(o.role_emoji, o.name),
          callback_data="do_assign:{}:{}".format(cid, o.id))] for o in ops]
    b.append([IKB(text="❌ Снять закрепление", callback_data="do_assign:{}:0".format(cid))])
    b.append([IKB(text="🔙", callback_data="view_candidate:{}".format(cid))])
    await cb.message.edit_text("👤 Закрепить за оператором:", reply_markup=IKM(inline_keyboard=b))
    await cb.answer()


@router.callback_query(F.data.startswith("do_assign:"))
async def cb_do_assign(cb: CallbackQuery, session: AsyncSession):
    parts = cb.data.split(":")
    cid, oid = int(parts[1]), int(parts[2])
    c = await session.get(Candidate, cid)
    if not c:
        await cb.answer("❌"); return
    c.assigned_operator_id = oid if oid > 0 else None
    await session.commit()
    await session.refresh(c)
    if oid > 0:
        op = await OperatorService(session).get_by_id(oid)
        await cb.answer("✅ {} → {}".format(c.full_name, op.name if op else "?"))
    else:
        await cb.answer("❌ Снято")


@router.message(Command("assign"))
async def cmd_assign(message: Message, session: AsyncSession):
    parts = message.text.strip().split()
    if len(parts) < 3:
        await message.answer("Формат: /assign <ID_кандидата> <ID_оператора>"); return
    try: cid, oid = int(parts[1]), int(parts[2])
    except: await message.answer("⚠️ Числовые ID"); return
    svc = OperatorService(session)
    c = await svc.assign_candidate(cid, oid)
    if c:
        op = await svc.get_by_id(oid)
        await message.answer("🔗 {} → {}".format(c.full_name, op.name if op else oid))
    else:
        await message.answer("❌ Не найдено")


# ══════════════════════════════════════════
# ── КАТЕГОРИИ ──
# ══════════════════════════════════════════

@router.callback_query(F.data == "cats_list")
async def cb_cats(cb: CallbackQuery, session: AsyncSession):
    result = await session.execute(select(Category).order_by(Category.name))
    cats = list(result.scalars().all())
    b = [[IKB(text="{} {} ({})".format(c.emoji, c.name, len(c.candidates)),
          callback_data="cat:{}".format(c.id))] for c in cats]
    b.append([IKB(text="➕ Новая категория", callback_data="cat_add")])
    b.append([IKB(text="🔙 Команда", callback_data="ops_list")])
    await cb.message.edit_text("📁 Категории:", reply_markup=IKM(inline_keyboard=b))
    await cb.answer()


@router.callback_query(F.data.startswith("cat:"))
async def cb_cat(cb: CallbackQuery, session: AsyncSession):
    cat = await session.get(Category, int(cb.data.split(":")[1]))
    if not cat:
        await cb.answer("❌"); return
    cands = [c for c in cat.candidates if not c.archived]
    lines = ["{} {} — {} кандидатов".format(cat.emoji, cat.name, len(cands))]
    if cat.description:
        lines.append(cat.description)
    for c in cands[:15]:
        lines.append("  • {} {}{}".format(c.full_name, c.ticket_emoji, c.medical_emoji))
    b = [[IKB(text="🗑 Удалить", callback_data="cat_del:{}".format(cat.id)),
          IKB(text="🔙 Категории", callback_data="cats_list")]]
    await cb.message.edit_text("\n".join(lines), reply_markup=IKM(inline_keyboard=b))
    await cb.answer()


@router.callback_query(F.data.startswith("cat_del:"))
async def cb_cat_del(cb: CallbackQuery, session: AsyncSession):
    cat = await session.get(Category, int(cb.data.split(":")[1]))
    if cat:
        await session.delete(cat)
        await session.commit()
    await cb.answer("🗑 Удалена")
    # Вернуться к списку
    result = await session.execute(select(Category).order_by(Category.name))
    cats = list(result.scalars().all())
    b = [[IKB(text="{} {} ({})".format(c.emoji, c.name, len(c.candidates)),
          callback_data="cat:{}".format(c.id))] for c in cats]
    b.append([IKB(text="➕ Новая", callback_data="cat_add"),
              IKB(text="🔙", callback_data="ops_list")])
    await cb.message.edit_text("📁 Категории:", reply_markup=IKM(inline_keyboard=b))


# FSM: Создать категорию
@router.callback_query(F.data == "cat_add")
@router.message(Command("add_category"))
async def cat_start(event, state: FSMContext):
    m = event if isinstance(event, Message) else event.message
    await state.set_state(CatFSM.name)
    await m.answer("📁 Название категории:")
    if isinstance(event, CallbackQuery): await event.answer()


@router.message(CatFSM.name)
async def cat_name(message: Message, state: FSMContext):
    await state.update_data(cat_name=message.text.strip())
    await state.set_state(CatFSM.emoji)
    await message.answer("🎨 Эмодзи для категории (или `-` для 📁):")


@router.message(CatFSM.emoji)
async def cat_emoji(message: Message, state: FSMContext, session: AsyncSession):
    emoji = message.text.strip() if message.text.strip() != "-" else "📁"
    data = await state.get_data(); await state.clear()
    cat = Category(name=data["cat_name"], emoji=emoji)
    session.add(cat)
    await session.commit()
    await session.refresh(cat)
    await message.answer("✅ Категория {} {} создана!".format(cat.emoji, cat.name))


# Назначение категории кандидату
@router.callback_query(F.data.startswith("set_cat:"))
async def cb_set_cat(cb: CallbackQuery, session: AsyncSession):
    cid = int(cb.data.split(":")[1])
    result = await session.execute(select(Category).order_by(Category.name))
    cats = list(result.scalars().all())
    b = [[IKB(text="{} {}".format(c.emoji, c.name),
          callback_data="do_cat:{}:{}".format(cid, c.id))] for c in cats]
    b.append([IKB(text="❌ Без категории", callback_data="do_cat:{}:0".format(cid))])
    b.append([IKB(text="🔙", callback_data="view_candidate:{}".format(cid))])
    await cb.message.edit_text("📁 Выберите категорию:", reply_markup=IKM(inline_keyboard=b))
    await cb.answer()


@router.callback_query(F.data.startswith("do_cat:"))
async def cb_do_cat(cb: CallbackQuery, session: AsyncSession):
    parts = cb.data.split(":")
    cid, cat_id = int(parts[1]), int(parts[2])
    c = await session.get(Candidate, cid)
    if not c:
        await cb.answer("❌"); return
    c.category_id = cat_id if cat_id > 0 else None
    await session.commit()
    if cat_id > 0:
        cat = await session.get(Category, cat_id)
        await cb.answer("✅ {} → {}".format(c.full_name, cat.name if cat else "?"))
    else:
        await cb.answer("❌ Категория снята")
