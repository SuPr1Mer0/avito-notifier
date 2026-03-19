import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database import init_db, is_seen, mark_seen
from parser import parse_avito

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class Form(StatesGroup):
    waiting_url = State()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот-уведомитель по Авито.\n\n"
        "Команды:\n"
        "/set_url — задать ссылку поиска\n"
        "/check — проверить новые объявления прямо сейчас\n"
        "/status — текущая ссылка"
    )


@dp.message(Command("set_url"))
async def cmd_set_url(message: Message, state: FSMContext):
    await message.answer("Пришли ссылку на поиск Авито (например https://www.avito.ru/belgorod?q=...):")
    await state.set_state(Form.waiting_url)


@dp.message(Form.waiting_url)
async def process_url(message: Message, state: FSMContext):
    url = message.text.strip()
    if "avito.ru" not in url:
        await message.answer("Это не похоже на ссылку Авито. Попробуй ещё раз.")
        return


    config.DEFAULT_SEARCH_URL = url  # ← временно, лучше в БД
    await message.answer(f"Ссылка сохранена!\n{url}")
    await state.clear()


@dp.message(Command("status"))
async def cmd_status(message: Message):
    await message.answer(f"Текущая ссылка:\n{config.DEFAULT_SEARCH_URL}")


@dp.message(Command("check"))
async def cmd_check(message: Message):
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("Доступ только владельцу.")
        return

    await message.answer("Начинаю проверку...")

    ads = await parse_avito(config.DEFAULT_SEARCH_URL)
    new_ads = []

    for ad in ads[:10]:
        if not await is_seen(ad["ad_id"]):
            new_ads.append(ad)
            await mark_seen(ad["ad_id"], ad["title"], ad["price"], ad["url"])

    if new_ads:
        text = "🆕 Новые объявления:\n\n"
        for ad in new_ads:
            text += f"{ad['title']}\n💰 {ad['price']}\n🔗 {ad['url']}\n\n"
        await message.answer(text)
    else:
        await message.answer("Новых объявлений не найдено.")


async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())