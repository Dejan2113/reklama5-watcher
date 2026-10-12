"""Превземање и парсирање огласи од reklama5.mk + филтрирање."""

import re
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.reklama5.mk"
SEARCH_URL = BASE_URL + "/Search/Index"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "mk-MK,mk;q=0.9,en;q=0.8",
}

CITIES = {
    1: "Скопје", 2: "Битола", 3: "Куманово", 4: "Прилеп", 5: "Тетово",
    6: "Велес", 7: "Штип", 8: "Охрид", 9: "Гостивар", 10: "Струмица",
    11: "Кавадарци", 12: "Кочани", 13: "Кичево", 14: "Струга",
}

CATEGORIES = {
    159: "Станови",
    158: "Куќи / Вили",
    161: "Викенд куќи",
    157: "Сите недвижнини",
}


# ------------------------------------------------------------------ парсирање

def parse_price(text):
    """'54.000 €' -> (54000, 'EUR'); 'По Договор' -> (None, None)."""
    text = " ".join((text or "").split())
    m = re.search(r"([\d.,]+)\s*(€|МКД|MKD|евра|ден)", text)
    if not m:
        return None, None
    number = int(re.sub(r"[.,]", "", m.group(1)))
    return number, ("EUR" if m.group(2) == "€" or "евра" else "MKD")


def parse_details(text):
    """'45 m² • 2,5 соби' -> (45.0, 2.5)."""
    m2 = rooms = None
    m = re.search(r"([\d.,]+)\s*m²", text or "")
    if m:
        m2 = float(m.group(1).replace(",", "."))
    r = re.search(r"([\d.,]+)\s*соб", text or "")
    if r:
        rooms = float(r.group(1).replace(",", "."))
    return m2, rooms


def parse_ads(html):
    soup = BeautifulSoup(html, "html.parser")
    ads = []
    for box in soup.select("div.ad-top-div"):
        link = box.select_one("a.SearchAdTitle")
        if not link:
            continue
        m_id = re.search(r"ad=(\d+)", link.get("href", ""))
        if not m_id:
            continue
        ad_id = m_id.group(1)

        price_el = box.select_one(".search-ad-price")
        price_text = " ".join(price_el.get_text().split()) if price_el else ""
        price, currency = parse_price(price_text)

        details = ""
        desc_div = box.select_one(".ad-desc-div")
        if desc_div:
            for p in desc_div.find_all("p", recursive=False):
                t = p.get_text(" ", strip=True)
                if "m²" in t or "соб" in t:
                    details = t
                    break
        m2, rooms = parse_details(details)

        image = None
        img_el = box.select_one(".ad-image")
        if img_el:
            m_img = re.search(r"url\(([^)]+)\)", img_el.get("style", ""))
            if m_img:
                image = m_img.group(1).strip("'\"")
                if image.startswith("//"):
                    image = "https:" + image

        date_el = box.select_one(".ad-date-div-1")
        date_text = ""
        if date_el:
            date_text = " ".join(date_el.get_text(" ", strip=True).split())

        desc_el = box.select_one(".searchAdDesc")
        city_el = box.select_one(".city-span")

        ads.append({
            "id": ad_id,
            "title": link.get_text(strip=True),
            "url": f"{BASE_URL}/AdDetails?ad={ad_id}",
            "price": price,
            "currency": currency,
            "price_text": price_text,
            "m2": m2,
            "rooms": rooms,
            "description": desc_el.get_text(" ", strip=True) if desc_el else "",
            "city": city_el.get_text(strip=True) if city_el else "",
            "image": image,
            "posted": date_text.replace("Промовирано", "").strip(),
            "promoted": box.select_one(".promotedBtn") is not None,
        })
    return ads


# ------------------------------------------------------------------ превземање

def search_url(search, page=1):
    """URL за пребарувањето директно на reklama5 (за копчето 'Отвори на сајтот')."""
    params = build_params(search, page)
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{SEARCH_URL}?{query}"


def build_params(search, page):
    params = {
        "cat": search["category_id"],
        "city": search["city_id"] or "",
        "q": "",
        "page": page,
    }
    if search["only_sale"]:
        params["sell"] = 1
    if search["price_min"]:
        params["priceFrom"] = search["price_min"]
    if search["price_max"]:
        params["priceTo"] = search["price_max"]
    return params


def fetch_page(search, page):
    resp = requests.get(SEARCH_URL, params=build_params(search, page),
                        headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def fetch_all(search):
    result, ids = [], set()
    for page in range(1, (search["max_pages"] or 5) + 1):
        ads = [a for a in parse_ads(fetch_page(search, page)) if a["id"] not in ids]
        if not ads:
            break
        for a in ads:
            ids.add(a["id"])
        result.extend(ads)
        time.sleep(2)  # учтиво кон сајтот
    return result


# ------------------------------------------------------------------ филтри

def _in_range(value, lo, hi):
    if lo is None and hi is None:
        return True
    if value is None:
        return False
    return (lo is None or value >= lo) and (hi is None or value <= hi)


def _words(text):
    return [w.strip().lower() for w in (text or "").split(",") if w.strip()]


def matches(ad, s):
    text = (ad["title"] + " " + ad["description"]).lower()

    if s["skip_promoted"] and ad["promoted"]:
        return False

    if s["price_min"] is not None or s["price_max"] is not None:
        if ad["currency"] != "EUR":
            return False
        if not _in_range(ad["price"], s["price_min"], s["price_max"]):
            return False

    if not _in_range(ad["m2"], s["m2_min"], s["m2_max"]):
        return False
    if not _in_range(ad["rooms"], s["rooms_min"], s["rooms_max"]):
        return False

    include = _words(s["include_words"])
    if include and not any(w in text for w in include):
        return False
    if any(w in text for w in _words(s["exclude_words"])):
        return False
    return True
