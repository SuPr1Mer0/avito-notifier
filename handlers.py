import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from urllib.parse import urlparse

import database as db
from config import MAX_SUBSCRIPTIONS_PER_USER
from parser import build_search_url, normalize_avito_url

logger = logging.getLogger(__name__)
router = Router()


# ─── FSM States ──────────────────────────────────────────────────────────────

class AddSubscription(StatesGroup):
    waiting_for_title = State()
    waiting_for_url = State()
    waiting_for_min_price = State()
    waiting_for_max_price = State()
    waiting_for_keywords = State()


# ─── Клавиатуры ───────────────────────────────────────────────────────────────

def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Мои подписки"), KeyboardButton(text="➕ Добавить подписку")],
            [KeyboardButton(text="🔔 Уведомления"), KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True
    )


def subscriptions_keyboard(subs: list) -> InlineKeyboardMarkup:
    buttons = []
    for sub in subs:
        row = [
            InlineKeyboardButton(text=f"🗑 {sub['title']}", callback_data=f"del_sub:{sub['id']}"),
            InlineKeyboardButton(text="🔍", callback_data=f"view_sub:{sub['id']}"),
        ]
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_delete_keyboard(sub_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Удалить", callback_data=f"confirm_del:{sub_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
    ]])


def skip_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⏭ Пропустить")]],
        resize_keyboard=True
    )


# ─── Команды ──────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    db.upsert_user(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.first_name or ""
    )
    await message.answer(
        "👋 <b>Добро пожаловать в Авито-уведомитель!</b>\n\n"
        "Я слежу за новыми объявлениями на Авито и мгновенно тебя уведомляю.\n\n"
        "🔸 Добавь подписку — укажи запрос или ссылку\n"
        "🔸 Настрой фильтры по цене и ключевым словам\n"
        "🔸 Получай уведомления о новых объявлениях\n\n"
        "Используй кнопки меню ниже 👇",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>Как пользоваться ботом:</b>\n\n"
        "1️⃣ Нажми <b>➕ Добавить подписку</b>\n"
        "2️⃣ Введи название подписки\n"
        "3️⃣ Вставь ссылку с Авито или введи поисковый запрос\n"
        "4️⃣ Настрой фильтры по цене (необязательно)\n"
        "5️⃣ Укажи ключевые слова для дополнительной фильтрации\n\n"
        "📌 <b>Команды:</b>\n"
        "/start — главное меню\n"
        "/add — добавить подписку\n"
        "/list — список подписок\n"
        "/help — эта справка\n\n"
        f"⚠️ Максимум подписок: <b>{MAX_SUBSCRIPTIONS_PER_USER}</b>",
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )


# ─── Список подписок ──────────────────────────────────────────────────────────

@router.message(F.text == "📋 Мои подписки")
@router.message(Command("list"))
async def cmd_list(message: Message):
    subs = db.get_subscriptions(message.from_user.id)
    if not subs:
        await message.answer(
            "📭 У тебя пока нет подписок.\n\n"
            "Нажми <b>➕ Добавить подписку</b>, чтобы начать отслеживать объявления.",
            parse_mode="HTML",
            reply_markup=main_keyboard()
        )
        return

    text = f"📋 <b>Твои подписки</b> ({len(subs)}/{MAX_SUBSCRIPTIONS_PER_USER}):\n\n"
    for i, sub in enumerate(subs, 1):
        price_info = ""
        if sub["min_price"] or sub["max_price"]:
            lo = f"{sub['min_price']:,}₽" if sub["min_price"] else "0"
            hi = f"{sub['max_price']:,}₽" if sub["max_price"] else "∞"
            price_info = f"\n   💰 {lo} — {hi}"
        kw_info = f"\n   🔑 {sub['keywords']}" if sub["keywords"] else ""
        text += f"{i}. <b>{sub['title']}</b>{price_info}{kw_info}\n"

    text += "\n👇 Нажми на кнопку, чтобы удалить подписку или посмотреть ссылку:"
    await message.answer(text, parse_mode="HTML", reply_markup=subscriptions_keyboard(subs))


# ─── Просмотр / удаление подписки ────────────────────────────────────────────

@router.callback_query(F.data.startswith("view_sub:"))
async def cb_view_sub(callback: CallbackQuery):
    sub_id = int(callback.data.split(":")[1])
    sub = db.get_subscription(sub_id, callback.from_user.id)
    if not sub:
        await callback.answer("Подписка не найдена.", show_alert=True)
        return

    price_info = ""
    if sub["min_price"] or sub["max_price"]:
        lo = f"{sub['min_price']:,}₽" if sub["min_price"] else "без минимума"
        hi = f"{sub['max_price']:,}₽" if sub["max_price"] else "без максимума"
        price_info = f"\n💰 Цена: {lo} — {hi}"

    text = (
        f"🔍 <b>{sub['title']}</b>\n"
        f"🔗 <a href='{sub['url']}'>Ссылка на поиск</a>"
        f"{price_info}"
    )
    if sub["keywords"]:
        text += f"\n🔑 Ключевые слова: {sub['keywords']}"

    await callback.message.answer(text, parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data.startswith("del_sub:"))
async def cb_delete_sub(callback: CallbackQuery):
    sub_id = int(callback.data.split(":")[1])
    sub = db.get_subscription(sub_id, callback.from_user.id)
    if not sub:
        await callback.answer("Подписка не найдена.", show_alert=True)
        return

    await callback.message.answer(
        f"🗑 Удалить подписку <b>{sub['title']}</b>?",
        parse_mode="HTML",
        reply_markup=confirm_delete_keyboard(sub_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del:"))
async def cb_confirm_delete(callback: CallbackQuery):
    sub_id = int(callback.data.split(":")[1])
    deleted = db.delete_subscription(sub_id, callback.from_user.id)
    if deleted:
        await callback.message.edit_text("✅ Подписка удалена.")
    else:
        await callback.message.edit_text("❌ Подписка не найдена.")
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery):
    await callback.message.edit_text("❌ Отменено.")
    await callback.answer()


# ─── Уведомления ──────────────────────────────────────────────────────────────

@router.message(F.text == "🔔 Уведомления")
async def cmd_notifications(message: Message):
    user = db.get_user(message.from_user.id)
    enabled = user["notifications_enabled"] if user else True

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🔕 Отключить" if enabled else "🔔 Включить",
            callback_data="toggle_notif"
        )
    ]])
    status = "✅ включены" if enabled else "❌ отключены"
    await message.answer(
        f"🔔 Уведомления сейчас <b>{status}</b>.\n\n"
        "Нажми кнопку, чтобы изменить:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "toggle_notif")
async def cb_toggle_notif(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    enabled = user["notifications_enabled"] if user else True
    db.set_notifications(callback.from_user.id, not enabled)
    new_status = "✅ включены" if not enabled else "❌ отключены"
    await callback.message.edit_text(f"🔔 Уведомления теперь <b>{new_status}</b>.", parse_mode="HTML")
    await callback.answer()


# ─── Добавление подписки — FSM ────────────────────────────────────────────────

@router.message(F.text == "➕ Добавить подписку")
@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    count = db.count_user_subscriptions(message.from_user.id)
    if count >= MAX_SUBSCRIPTIONS_PER_USER:
        await message.answer(
            f"⚠️ Достигнут лимит подписок ({MAX_SUBSCRIPTIONS_PER_USER}).\n"
            "Удали ненужные, чтобы добавить новые.",
            reply_markup=main_keyboard()
        )
        return

    await state.set_state(AddSubscription.waiting_for_title)
    await message.answer(
        "📝 Введи <b>название</b> для подписки\n"
        "(например: <i>iPhone 13, Диван IKEA, Велосипед</i>)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(AddSubscription.waiting_for_title)
async def fsm_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if len(title) < 2 or len(title) > 100:
        await message.answer("⚠️ Название должно быть от 2 до 100 символов. Попробуй снова:")
        return

    await state.update_data(title=title)
    await state.set_state(AddSubscription.waiting_for_url)
    await message.answer(
        "🔗 Теперь вставь <b>ссылку с Авито</b> или введи <b>поисковый запрос</b>.\n\n"
        "Примеры:\n"
        "• <code>https://www.avito.ru/moskva?q=iphone+13</code>\n"
        "• <code>iPhone 13 128GB</code> (бот построит ссылку сам)\n\n"
        "💡 Совет: сначала найди нужное на сайте, скопируй URL со всеми фильтрами.",
        parse_mode="HTML"
    )


@router.message(AddSubscription.waiting_for_url)
async def fsm_url(message: Message, state: FSMContext):
    text = message.text.strip()

    # Определяем: это URL или поисковый запрос
    if text.startswith("http") and "avito.ru" in text:
        url = normalize_avito_url(text)
    elif "avito.ru" in text:
        url = "https://" + text
        url = normalize_avito_url(url)
    else:
        # Строим URL из поискового запроса
        url = build_search_url(text)

    await state.update_data(url=url)
    await state.set_state(AddSubscription.waiting_for_min_price)
    await message.answer(
        "💰 Укажи <b>минимальную цену</b> (в рублях) или пропусти:",
        parse_mode="HTML",
        reply_markup=skip_keyboard()
    )


@router.message(AddSubscription.waiting_for_min_price)
async def fsm_min_price(message: Message, state: FSMContext):
    text = message.text.strip()
    min_price = None

    if text != "⏭ Пропустить":
        digits = "".join(c for c in text if c.isdigit())
        if not digits:
            await message.answer("⚠️ Введи число или нажми «Пропустить»:")
            return
        min_price = int(digits)

    await state.update_data(min_price=min_price)
    await state.set_state(AddSubscription.waiting_for_max_price)
    await message.answer(
        "💰 Укажи <b>максимальную цену</b> (в рублях) или пропусти:",
        parse_mode="HTML",
        reply_markup=skip_keyboard()
    )


@router.message(AddSubscription.waiting_for_max_price)
async def fsm_max_price(message: Message, state: FSMContext):
    text = message.text.strip()
    max_price = None

    if text != "⏭ Пропустить":
        digits = "".join(c for c in text if c.isdigit())
        if not digits:
            await message.answer("⚠️ Введи число или нажми «Пропустить»:")
            return
        max_price = int(digits)

    data = await state.get_data()
    min_price = data.get("min_price")
    if min_price and max_price and max_price < min_price:
        await message.answer(
            f"⚠️ Максимальная цена ({max_price:,}₽) меньше минимальной ({min_price:,}₽). Введи снова:"
        )
        return

    await state.update_data(max_price=max_price)
    await state.set_state(AddSubscription.waiting_for_keywords)
    await message.answer(
        "🔑 Введи <b>ключевые слова</b> для дополнительной фильтрации через запятую,\n"
        "или пропусти этот шаг.\n\n"
        "Пример: <code>новый, оригинал, срочно</code>",
        parse_mode="HTML",
        reply_markup=skip_keyboard()
    )


@router.message(AddSubscription.waiting_for_keywords)
async def fsm_keywords(message: Message, state: FSMContext):
    text = message.text.strip()
    keywords = None if text == "⏭ Пропустить" else text

    data = await state.get_data()
    sub_id = db.add_subscription(
        user_id=message.from_user.id,
        title=data["title"],
        url=data["url"],
        min_price=data.get("min_price"),
        max_price=data.get("max_price"),
        keywords=keywords
    )

    # Формируем подтверждение
    price_info = ""
    if data.get("min_price") or data.get("max_price"):
        lo = f"{data['min_price']:,}₽" if data.get("min_price") else "0"
        hi = f"{data['max_price']:,}₽" if data.get("max_price") else "∞"
        price_info = f"\n💰 Цена: {lo} — {hi}"

    kw_info = f"\n🔑 Ключевые слова: {keywords}" if keywords else ""

    await state.clear()
    await message.answer(
        f"✅ <b>Подписка добавлена!</b>\n\n"
        f"📌 {data['title']}"
        f"{price_info}"
        f"{kw_info}\n\n"
        f"🔔 Я буду уведомлять тебя о новых объявлениях.",
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )
