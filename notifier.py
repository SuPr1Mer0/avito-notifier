import logging
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from parser import Ad

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 1024


def format_ad_message(ad: Ad, subscription_title: str) -> str:
    """Форматируем сообщение об объявлении."""
    price_str = ""
    if ad.price:
        price_str = f"💰 <b>{ad.price:,} ₽</b>".replace(",", " ")
    elif ad.price_text:
        price_str = f"💰 {ad.price_text}"
    else:
        price_str = "💰 Цена не указана"

    location_str = f"📍 {ad.location}" if ad.location else ""
    desc_str = f"\n📄 {ad.description[:150]}..." if ad.description else ""

    parts = [
        f"🆕 <b>Новое объявление</b> по подписке «{subscription_title}»",
        "",
        f"📦 <b>{ad.title}</b>",
        price_str,
    ]
    if location_str:
        parts.append(location_str)
    if desc_str:
        parts.append(desc_str)
    parts.extend(["", f"🔗 <a href='{ad.url}'>Открыть объявление</a>"])

    return "\n".join(parts)


async def send_ad_notification(bot: Bot, user_id: int, ad: Ad, subscription_title: str):
    """Отправляем уведомление пользователю."""
    text = format_ad_message(ad, subscription_title)

    try:
        # Пробуем с фото
        if ad.image_url:
            try:
                await bot.send_photo(
                    chat_id=user_id,
                    photo=ad.image_url,
                    caption=text[:MAX_MESSAGE_LENGTH],
                    parse_mode="HTML"
                )
                return
            except Exception:
                pass  # Если фото не загрузилось — отправим текстом

        # Текстовое сообщение
        await bot.send_message(
            chat_id=user_id,
            text=text[:MAX_MESSAGE_LENGTH],
            parse_mode="HTML",
            disable_web_page_preview=False
        )

    except TelegramForbiddenError:
        logger.warning(f"Пользователь {user_id} заблокировал бота.")
    except TelegramBadRequest as e:
        logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
    except Exception as e:
        logger.error(f"Неизвестная ошибка отправки {user_id}: {e}")
