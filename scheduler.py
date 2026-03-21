import logging
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import aiohttp

import database as db
from parser import fetch_ads, filter_ads_by_price, filter_ads_by_keywords
from config import CHECK_INTERVAL_MINUTES
from notifier import send_ad_notification

logger = logging.getLogger(__name__)


async def check_subscriptions(bot: Bot):
    """Основная функция проверки всех активных подписок."""
    subscriptions = db.get_all_active_subscriptions()
    if not subscriptions:
        return

    logger.info(f"Проверяем {len(subscriptions)} подписок...")

    async with aiohttp.ClientSession() as session:
        for sub in subscriptions:
            try:
                await process_subscription(bot, session, sub)
            except Exception as e:
                logger.error(f"Ошибка при обработке подписки {sub['id']}: {e}")

    # Периодически чистим старые записи
    db.cleanup_old_seen_ads(days=30)
    logger.info("Проверка завершена.")


async def process_subscription(bot: Bot, session: aiohttp.ClientSession, sub):
    """Обрабатываем одну подписку."""
    sub_id = sub["id"]
    user_id = sub["user_id"]

    # Получаем объявления
    ads = await fetch_ads(session, sub["url"])
    if not ads:
        return

    # Фильтруем по цене и ключевым словам
    ads = filter_ads_by_price(ads, sub["min_price"], sub["max_price"])
    if sub["keywords"]:
        ads = filter_ads_by_keywords(ads, sub["keywords"])

    # Отправляем только новые объявления
    new_count = 0
    for ad in ads:
        if db.is_ad_seen(sub_id, ad.id):
            continue

        db.mark_ad_seen(sub_id, ad.id)
        await send_ad_notification(bot, user_id, ad, sub["title"])
        new_count += 1

        # Не более 5 уведомлений за один цикл на подписку
        if new_count >= 5:
            break

    if new_count:
        logger.info(f"Подписка {sub_id} ({sub['title']}): отправлено {new_count} уведомлений пользователю {user_id}")


async def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Запускаем планировщик."""
    db.init_db()

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        check_subscriptions,
        trigger="interval",
        minutes=CHECK_INTERVAL_MINUTES,
        args=[bot],
        id="check_ads",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Планировщик запущен. Интервал: {CHECK_INTERVAL_MINUTES} минут.")
    return scheduler
