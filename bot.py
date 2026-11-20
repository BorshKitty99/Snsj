import json, os, re, sys, time
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

# ===== НАСТРОЙКИ =====
CITY = "rossiya"          # rossiya = вся Россия, или moskva, sankt-peterburg и т.д.
MAX_PRICE = 2000
QUERIES = ["nukeproof вынос", "funn вынос", "race face вынос"]
BRANDS = ["nukeproof", "нукепруф", "funn", "фанн", "race face", "raceface", "рейс фейс", "рейсфейс"]
MAX_PER_RUN = 10          # максимум сообщений за один запуск
# ======================

TOKEN = os.environ["TG_TOKEN"]
CHAT = os.environ["TG_CHAT"]
import random
PROXY_LIST = []
for line in os.environ.get("PROXY", "").splitlines():
    line = line.strip()
    if line:
        PROXY_LIST.append(line if "://" in line else "http://" + line)
random.shuffle(PROXY_LIST)
GOOD = []  # рабочие прокси из этого запуска
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


def tg(text):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  data={"chat_id": CHAT, "text": text}, timeout=20)


def load():
    try:
        return json.load(open("seen.json"))
    except Exception:
        return {"seen": [], "blocked": False}


def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for it in soup.select('[data-marker="item"]'):
        a = it.select_one('[data-marker="item-title"]') or it.select_one("a[href]")
        if not a or not a.get("href"):
            continue
        p = it.select_one('[itemprop="price"]')
        try:
            price = int(p.get("content"))
        except Exception:
            price = 0
        items.append({
            "id": it.get("data-item-id") or a["href"],
            "title": a.get_text(" ", strip=True),
            "url": "https://www.avito.ru" + a["href"].split("?")[0],
            "price": price,
            "text": it.get_text(" ", strip=True).lower(),
        })
    return items


def fetch(query):
    url = f"https://www.avito.ru/{CITY}?q={quote(query)}&pmax={MAX_PRICE}&s=104"
    tries = GOOD + [p for p in PROXY_LIST if p not in GOOD][:25] if PROXY_LIST else [None]
    last = "нет ответа"
    for px in tries:
        try:
            r = requests.get(url, headers=HEADERS, timeout=12,
                             proxies={"http": px, "https": px} if px else None)
        except Exception:
            last = "прокси не отвечает"
            continue
        if r.status_code != 200:
            last = r.status_code
            continue
        items = parse(r.text)
        if items:
            if px and px not in GOOD:
                GOOD.append(px)
            return items, 200
        last = "нет объявлений (капча?)"
    return None, last


def main():
    st = load()
    seen = set(st["seen"])
    found, errors = [], []
    for q in QUERIES:
        items, code = fetch(q)
        if items is None:
            errors.append(f"{q}: {code}")
        else:
            found += items
        time.sleep(3)

    if errors and len(errors) == len(QUERIES):
        if not st["blocked"]:
            tg("⚠️ Авито блокирует бота: " + "; ".join(errors))
        st["blocked"] = True
        json.dump(st, open("seen.json", "w"))
        return
    st["blocked"] = False

    sent = 0
    for it in found:
        if it["id"] in seen or sent >= MAX_PER_RUN:
            continue
        t = it["text"]
        if not any(b in t for b in BRANDS):
            seen.add(it["id"])
            continue
        if not (0 < it["price"] <= MAX_PRICE):
            seen.add(it["id"])
            continue
        d = bool(re.search(r"31[.,]8", t))
        l = bool(re.search(r"(?<!\d)35(?!\d)", t))
        mark = "✅ Точно: 31.8 и 35" if d and l else "⚠️ Размер не подтверждён, уточните у продавца"
        tg(f"🔔 {it['title']}\n💰 {it['price']} ₽\n{mark}\n🔗 {it['url']}")
        seen.add(it["id"])
        sent += 1

    st["seen"] = list(seen)[-3000:]
    json.dump(st, open("seen.json", "w"))


if __name__ == "__main__":
    main()
