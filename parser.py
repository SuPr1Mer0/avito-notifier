import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import re


async def parse_avito(url: str) -> list[dict]:
    headers = {"User-Agent": UserAgent().random}

    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"Ошибка запроса: {e}")
        return []

    soup = BeautifulSoup(r.text, "lxml")

    items = []
    for item in soup.select('div[data-marker="item"]'):
        try:
            title_tag = item.select_one('h3[itemprop="name"]')
            title = title_tag.get_text(strip=True) if title_tag else "Без названия"

            price_tag = item.select_one('meta[itemprop="price"]')
            price = price_tag["content"] if price_tag else item.select_one('span[data-marker="item-price"]')
            price = price.get_text(strip=True) if hasattr(price, "get_text") else price or "Цена не указана"

            link_tag = item.select_one('a[data-marker="item-title"]')
            relative_url = link_tag["href"] if link_tag else ""
            full_url = "https://www.avito.ru" + relative_url if relative_url else ""

            # ID объявления — обычно в url
            ad_id_match = re.search(r"_(\d+)", relative_url)
            ad_id = ad_id_match.group(1) if ad_id_match else None

            if ad_id and full_url:
                items.append({
                    "ad_id": ad_id,
                    "title": title,
                    "price": price,
                    "url": full_url
                })
        except:
            continue

    return items