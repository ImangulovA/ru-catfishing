#!/usr/bin/env python3
"""Seed the candidate pool with NON-PERSON "realia": sports, phenomena, objects,
plus WORKS (bands, albums, novels, paintings) instead of the artists behind them.

fetch_top.py seeds from most-viewed articles, which skews heavily to people
(celebrities dominate pageviews). Music/literature/art end up ~70-77% people
because the seed pulls artists, not their works. This script walks a curated set
of ru.wiki CATEGORIES (recursing subcategories a couple levels, since the real
lists live in "...по алфавиту" subcats), collects article titles, then keeps only
the FAMOUS ones (pv >= PV_FLOOR) so downstream classify does not waste category
fetches on obscure entries.

Two stages:
  --gather   : BFS categories -> prototype/data/_realia_raw.json (+ counts). Cheap.
  (default)  : gather (or reuse raw) -> resolve_title + pageviews prefilter ->
               prototype/data/_realia_titles.json (famous realia only).

classify_pool.py folds _realia_titles.json in alongside _top_titles.json.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import classify
from classify import PV_FLOOR, PV_START, PV_END

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "prototype", "data")
RAW = os.path.join(DATA, "_realia_raw.json")
OUT = os.path.join(DATA, "_realia_titles.json")
UA = "game-designer/0.1 (personal project; imangulovamal@gmail.com)"

MAX_DEPTH = 2          # subcategory recursion depth
MAX_PER_SEED = 700     # cap pages collected per seed category (across subcats)

# Curated realia categories. Grouped by intent; the value is the recursion depth
# override (None -> MAX_DEPTH). Big "по алфавиту" trees are capped by MAX_PER_SEED.
SEED_CATS = [
    # --- WORKS to fix the music people-skew (bands, not artists) ---
    "Рок-группы", "Хип-хоп-группы", "Метал-группы", "Поп-группы",
    "Панк-рок-группы", "Музыкальные коллективы по алфавиту",
    # --- WORKS to fix the literature people-skew (novels, not writers) ---
    "Фантастические романы", "Романы-антиутопии",
    "Сказки", "Поэмы", "Пьесы",
    # --- WORKS to fix the art people-skew (paintings, not painters) ---
    "Картины по алфавиту", "Скульптуры по алфавиту", "Фрески",
    # --- sports as TYPES / events, not athletes ---
    "Виды спорта", "Единоборства", "Олимпийские виды спорта",
    "Зимние виды спорта", "Командные виды спорта",
    # --- fun realia: creatures, nature, food, animals, space, objects ---
    "Мифические существа", "Драконы", "Природные явления", "Стихийные бедствия",
    "Блюда по алфавиту", "Напитки", "Алкогольные напитки", "Десерты", "Сыры",
    "Породы собак по алфавиту", "Породы кошек", "Динозавры",
    "Химические элементы", "Планеты Солнечной системы", "Созвездия",
    "Музыкальные инструменты", "Праздники по алфавиту", "Настольные игры",
    "Пилотируемые космические аппараты", "Автомобили по маркам",
    "Небоскрёбы", "Мосты по алфавиту", "Всемирное наследие по алфавиту",
    # --- abstract "realia": concepts, phenomena, biases ---
    "Когнитивные искажения", "Психологические понятия", "Философские теории",
    "Логические ошибки", "Единицы измерения",
    # --- BATCH 2 (2026-07-03): widen the raw pool by ~5-7k, unprocessed ---
    # nature / animals / plants
    "Млекопитающие", "Птицы", "Рыбы", "Растения по алфавиту", "Насекомые",
    "Деревья",
    # geography / places
    "Столицы государств", "Города", "Реки по алфавиту", "Горы", "Вулканы",
    "Острова по алфавиту", "Озёра по алфавиту", "Замки по алфавиту", "Соборы",
    "Метрополитены",
    # works: screen / stage / animation / games
    "Телесериалы по алфавиту", "Мультфильмы по алфавиту", "Аниме",
    "Компьютерные игры по алфавиту", "Оперы по алфавиту", "Балеты",
    "Музыкальные альбомы", "Песни по алфавиту",
    # food / drink / objects / concepts
    "Коктейли по алфавиту", "Минералы по алфавиту", "Драгоценные камни",
    "Боги по алфавиту", "Заболевания по алфавиту",
]

SKIP_PREFIX = ("Список", "Служебная", "Special", "Категория", "Шаблон",
               "Википедия", "Портал", "Файл", "Проект")
# subcategory names we never descend into (meta / person buckets / by-country noise)
SKIP_SUBCAT = ("Персоналии", "по странам", "по годам", "в искусстве",
               "в культуре", "в филателии", "Википедия", "Изображения",
               "Категории")


def is_junk(title):
    if ":" in title:
        return True
    if any(title.startswith(p) for p in SKIP_PREFIX):
        return True
    if re.fullmatch(r"[\d\W]+", title):
        return True
    return False


def api(params):
    params = {**params, "format": "json", "formatversion": "2"}
    url = "https://ru.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    delay = 2
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 5:
                time.sleep(delay)
                delay *= 2  # 2,4,8,16,32s backoff
                continue
            raise


def members(cat, cmtype):
    """All category members of the given type, following continuation."""
    out = []
    cont = {}
    while True:
        data = api({"action": "query", "list": "categorymembers",
                    "cmtitle": "Категория:" + cat, "cmtype": cmtype,
                    "cmlimit": "500", **cont})
        out += [m["title"] for m in data.get("query", {}).get("categorymembers", [])]
        cont = data.get("continue", {})
        if not cont:
            return out
        time.sleep(0.3)


def gather_seed(seed, cap=MAX_PER_SEED, max_depth=MAX_DEPTH):
    """BFS a category tree; return a set of article titles (namespace 0)."""
    pages = set()
    frontier = [(seed, 0)]
    seen_cats = {seed}
    while frontier and len(pages) < cap:
        cat, depth = frontier.pop(0)
        try:
            for t in members(cat, "page"):
                if not is_junk(t):
                    pages.add(t)
                    if len(pages) >= cap:
                        break
        except Exception as e:
            print(f"    page ERR {cat!r}: {e}", file=sys.stderr)
        if depth < max_depth:
            try:
                for sc in members(cat, "subcat"):
                    name = sc.split(":", 1)[1] if ":" in sc else sc
                    if name in seen_cats:
                        continue
                    if any(s in name for s in SKIP_SUBCAT):
                        continue
                    seen_cats.add(name)
                    frontier.append((name, depth + 1))
            except Exception as e:
                print(f"    subcat ERR {cat!r}: {e}", file=sys.stderr)
        time.sleep(0.3)
    return pages


def do_gather():
    # merge into existing raw; only (re)fetch seeds that have no members yet
    allp = {}
    if os.path.exists(RAW):
        allp = json.load(open(RAW, encoding="utf-8"))
    for i, seed in enumerate(SEED_CATS, 1):
        if allp.get(seed):
            print(f"  [{i}/{len(SEED_CATS)}] {seed}: {len(allp[seed])} (cached)",
                  file=sys.stderr)
            continue
        p = gather_seed(seed)
        allp[seed] = sorted(p)
        json.dump(allp, open(RAW, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)  # checkpoint each seed
        print(f"  [{i}/{len(SEED_CATS)}] {seed}: {len(p)}", file=sys.stderr)
    json.dump(allp, open(RAW, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    uniq = sorted({t for lst in allp.values() for t in lst})
    print(f"\ngathered {len(uniq)} unique realia titles across "
          f"{len(SEED_CATS)} seeds -> {RAW}")
    return uniq


def pv_rest(title):
    """Average monthly ru.wiki pageviews via the REST API on the RAW title (no
    ru.wiki redirect resolve -> avoids api.php 429s; category members are already
    canonical). Cached in classify._PV so classify_pool gets a cache hit."""
    if title in classify._PV:
        return classify._PV[title]
    enc = urllib.parse.quote(title.replace(" ", "_"), safe="")
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
           f"ru.wikipedia/all-access/all-agents/{enc}/monthly/{PV_START}/{PV_END}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    val = 0.0
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                items = json.load(r).get("items", [])
            if items:
                val = sum(it.get("views", 0) for it in items) / len(items)
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break  # no data -> obscure -> 0
            if e.code == 429 and attempt < 3:
                time.sleep(2 * (attempt + 1))
                continue
            break
        except Exception:
            break
    classify._PV[title] = val
    return val


def do_filter(titles):
    """Keep famous realia (pv >= PV_FLOOR). Warms _pageviews_cache.json."""
    kept = []
    total = len(titles)
    for n, t in enumerate(titles, 1):
        if pv_rest(t) >= PV_FLOOR:
            kept.append(t)
        if n % 200 == 0:
            print(f"  pv-filtered {n}/{total} (kept {len(kept)})", file=sys.stderr)
            classify._save_pv_cache(classify._PV)
        time.sleep(0.02)
    classify._save_pv_cache(classify._PV)
    kept = sorted(set(kept))
    json.dump(kept, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nwrote {len(kept)} famous realia (pv>={PV_FLOOR}) -> {OUT}")


def main():
    if "--gather" in sys.argv:
        do_gather()
        return
    if os.path.exists(RAW) and "--refetch" not in sys.argv:
        raw = json.load(open(RAW, encoding="utf-8"))
        titles = sorted({t for lst in raw.values() for t in lst})
        print(f"reusing {len(titles)} gathered titles from {RAW}", file=sys.stderr)
    else:
        titles = do_gather()
    do_filter(titles)


if __name__ == "__main__":
    main()
