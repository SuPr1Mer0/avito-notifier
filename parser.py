import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import aiohttp
from bs4 import BeautifulSoup

from config import USER_AGENT, REQUEST_DELAY

logger = logging.getLogger(__name__)


@dataclass
class Ad:
    id: str
    title: str
    price: Optional[int]
    price_text: str
    url: str
    location: str
    image_url: Optional[str]
    description: str


def build_search_url(query: str, min_price: int = None, max_price: int = None,
                     category: str = None, region: str = "rossiya") -> str:
    base = f"https://www.avito.ru/{region}"
    if category:
        base += f"/{category}"

    params = {"q": query}
    if min_price:
        params["pmin"] = min_price
    if max_price:
        params["pmax"] = max_price

    return f"{base}?{urlencode(params)}"


def normalize_avito_url(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    keep = {"q", "pmin", "pmax", "cd", "s", "localPriority"}
    filtered = {k: v for k, v in params.items() if k in keep}
    new_query = urlencode({k: v[0] for k, v in filtered.items()})
    return urlunparse(parsed._replace(query=new_query))


def extract_price(price_str: str) -> Optional[int]:
    if not price_str:
        return None
    digits = re.sub(r"[^\d]", "", price_str)
    return int(digits) if digits else None


async def fetch_ads(session: aiohttp.ClientSession, url: str) -> list[Ad]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    await asyncio.sleep(REQUEST_DELAY)

    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                logger.warning(f"Авито вернул статус {resp.status} для {url}")
                return []
            html = await resp.text()
    except asyncio.TimeoutError:
        logger.error(f"Таймаут при запросе {url}")
        return []
    except Exception as e:
        logger.error(f"Ошибка при запросе {url}: {e}")
        return []

    return parse_ads_from_html(html)


def parse_ads_from_html(html: str) -> list[Ad]:
    soup = BeautifulSoup(html, "html.parser")
    ads = []

    items = soup.select("[data-marker='item']")

    if not items:
        items = soup.select(".iva-item-root")

    for item in items:
        try:
            ad = parse_single_ad(item)
            if ad:
                ads.append(ad)
        except Exception as e:
            logger.debug(f"Ошибка парсинга карточки: {e}")

    logger.info(f"Найдено {len(ads)} объявлений")
    return ads


def parse_single_ad(item) -> Optional[Ad]:
    ad_id = item.get("data-item-id") or item.get("id", "")
    if not ad_id:
        link_el = item.select_one("a[href*='/']")
        if link_el:
            href = link_el.get("href", "")
            m = re.search(r"_(\d+)$", href.rstrip("/"))
            ad_id = m.group(1) if m else href

    if not ad_id:
        return None

    title_el = (
        item.select_one("[itemprop='name']") or
        item.select_one("[data-marker='item-title']") or
        item.select_one(".title-root") or
        item.select_one("h3")
    )
    title = title_el.get_text(strip=True) if title_el else "Без названия"

    link_el = item.select_one("a[href]")
    href = link_el["href"] if link_el else ""
    if href and not href.startswith("http"):
        href = "https://www.avito.ru" + href
    ad_url = href

    price_el = (
        item.select_one("[data-marker='item-price']") or
        item.select_one("[class*='price']") or
        item.select_one("meta[itemprop='price']")
    )
    if price_el:
        price_text = price_el.get("content") or price_el.get_text(strip=True)
    else:
        price_text = "Цена не указана"
    price = extract_price(price_text)

    location_el = (
        item.select_one("[data-marker='item-location']") or
        item.select_one("[class*='geo']") or
        item.select_one("span[class*='location']")
    )
    location = location_el.get_text(strip=True) if location_el else ""

    desc_el = item.select_one("[class*='description']")
    description = desc_el.get_text(strip=True)[:200] if desc_el else ""

    img_el = item.select_one("img[src]")
    image_url = img_el["src"] if img_el else None
    if image_url and image_url.startswith("//"):
        image_url = "https:" + image_url

    return Ad(
        id=str(ad_id),
        title=title,
        price=price,
        price_text=price_text,
        url=ad_url,
        location=location,
        image_url=image_url,
        description=description,
    )


def filter_ads_by_price(ads: list[Ad], min_price: int = None, max_price: int = None) -> list[Ad]:
    result = []
    for ad in ads:
        if ad.price is None:
            result.append(ad)
            continue
        if min_price and ad.price < min_price:
            continue
        if max_price and ad.price > max_price:
            continue
        result.append(ad)
    return result


def filter_ads_by_keywords(ads: list[Ad], keywords: str) -> list[Ad]:
    if not keywords:
        return ads
    kw_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
    result = []
    for ad in ads:
        text = (ad.title + " " + ad.description).lower()
        if any(kw in text for kw in kw_list):
            result.append(ad)
    return result
