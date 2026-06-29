#!/usr/bin/env python3
"""Theme + difficulty classification for ru-catfishing puzzles.

Two author-only signals used by compose_days.py to build balanced days:

  THEME  — one of 10 domains, from keyword rules over an article's categories.
  DIFFICULTY — a tier (easy/medium/hard) from a score combining Wikipedia
               pageviews (fame proxy) + number of useful categories (more clues
               = easier). Tiers are cut by PERCENTILE over the pool, so each pool
               is split into roughly equal thirds (robust to absolute spread).

pageviews are fetched from the Wikimedia REST API and cached to disk
(_pageviews_cache.json) so re-runs are fast and don't hammer the API.
"""
import json
import math
import os
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "prototype", "data")
PV_CACHE = os.path.join(DATA, "_pageviews_cache.json")

UA = "game-designer/0.1 (personal project; imangulovamal@gmail.com)"

# 12-month window for averaging pageviews (fixed for reproducibility).
PV_START = "20250601"
PV_END = "20260601"


# ---------------------------------------------------------------- THEME -------
# Ordered list (key, label, keyword-substrings). First theme with any keyword
# found in ANY of the article's categories (lowercased) wins. Order resolves
# overlaps (a footballer -> sport before person/society; a film director ->
# cinema). "society" is the fallback bucket.
THEMES = [
    ("games", "Игры", [
        "компьютерные игры", "видеоигр", "игры для", "игровые", "шутеры",
        "стратегии", "квесты", "ролевые игры", "игровые движки",
    ]),
    ("cinema", "Кино и сериалы", [
        "фильмы", "кинофильм", "сериал", "телесериал", "мультфильм",
        "мультсериал", "кинорежисс", "актёр", "актрис", "кинематограф",
        "оскар", "кинопрем", "режиссёр",
    ]),
    ("music", "Музыка", [
        "музык", "композитор", "певц", "певиц", "музыкальные группы",
        "альбом", "оперы", "симфони", "песни", "рок-", "джаз", "балет",
        "дирижёр", "музыканты",
    ]),
    ("art", "Искусство", [
        "картин", "живопис", "художник", "скульптур", "архитектор",
        "архитектур", "здания", "сооружения", "музе", "изобразительное",
        "фрески", "графики",
    ]),
    ("literature", "Литература", [
        "романы", "книги", "повести", "писател", "поэт", "литератур",
        "рассказы", "пьес", "стихотвор", "новеллы", "сказки", "эпос",
    ]),
    ("sport", "Спорт", [
        "спортсмен", "футбол", "хоккей", "теннис", "олимпийск", "шахмат",
        "баскетбол", "лёгкая атлетика", "бокс", "автогонщ", "спортивные",
        "чемпионы", "гимнаст",
    ]),
    ("science", "Наука и техника", [
        "учёные", "физик", "хими", "математик", "биолог", "астроном",
        "изобрет", "космонавт", "космическ", "техник", "инженер", "медицин",
        "наук", "философ", "палеонтолог", "динозавр", "элементы", "теорем",
    ]),
    ("history", "История и события", [
        "битв", "сражени", "войны", "революци", "импер", "корол", "цар",
        "династи", "монарх", "восстани", "историческ", "средневеков",
        "античн", "полководц", "правител", "князья",
    ]),
    ("geography", "География и природа", [
        "города", "страны", "реки", "озёра", "горы", "острова", "география",
        "населённые пункты", "животные", "птицы", "растения", "млекопитающ",
        "природ", "географ", "вулкан", "заповедник", "насеком", "рыбы",
    ]),
]
FALLBACK_THEME = ("society", "Общество/Прочее")
THEME_LABELS = {k: lbl for k, lbl, _ in THEMES}
THEME_LABELS[FALLBACK_THEME[0]] = FALLBACK_THEME[1]


def classify_theme(categories):
    """Return a theme key for an article given its (filtered) categories."""
    blob = " · ".join(categories).lower()
    for key, _label, kws in THEMES:
        if any(kw in blob for kw in kws):
            return key
    return FALLBACK_THEME[0]


# ------------------------------------------------------------ PAGEVIEWS -------
def _load_pv_cache():
    if os.path.exists(PV_CACHE):
        try:
            return json.load(open(PV_CACHE, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_pv_cache(cache):
    json.dump(cache, open(PV_CACHE, "w", encoding="utf-8"), ensure_ascii=False)


_PV = _load_pv_cache()


def fetch_pageviews(title, sleep=0.1):
    """Average monthly ru.wiki pageviews over the fixed window, cached.

    Returns a float (0.0 if the API has no data — usually a very obscure page).
    """
    if title in _PV:
        return _PV[title]
    enc = urllib.parse.quote(title.replace(" ", "_"), safe="")
    url = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        f"ru.wikipedia/all-access/all-agents/{enc}/monthly/{PV_START}/{PV_END}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    val = 0.0
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        items = data.get("items", [])
        if items:
            val = sum(it.get("views", 0) for it in items) / len(items)
    except urllib.error.HTTPError as e:
        if e.code != 404:  # 404 = no data for this article; treat as 0 (obscure)
            time.sleep(min(10, sleep * 10))
    except Exception:
        pass
    _PV[title] = val
    if len(_PV) % 25 == 0:
        _save_pv_cache(_PV)
    time.sleep(sleep)
    return val


def flush_pv_cache():
    _save_pv_cache(_PV)


# ------------------------------------------------------------ DIFFICULTY ------
def difficulty_score(pageviews, n_cats):
    """Higher score = easier (more famous + more clue categories)."""
    return math.log10(pageviews + 1.0) + 0.15 * n_cats


def assign_tiers(scores):
    """Map a list of (key, score) -> {key: 'easy'|'medium'|'hard'} by terciles.

    Top third of scores = easy (most famous), bottom third = hard.
    """
    if not scores:
        return {}
    ordered = sorted(scores, key=lambda kv: kv[1])  # ascending: hardest first
    n = len(ordered)
    cut1 = n // 3
    cut2 = 2 * n // 3
    tiers = {}
    for idx, (key, _score) in enumerate(ordered):
        if idx < cut1:
            tiers[key] = "hard"
        elif idx < cut2:
            tiers[key] = "medium"
        else:
            tiers[key] = "easy"
    return tiers


if __name__ == "__main__":
    # tiny self-test of the theme classifier
    samples = {
        "Бешеные псы": ["Фильмы 1992 года", "Криминальные фильмы США"],
        "Бергкамп": ["Футболисты Нидерландов", "Игроки ФК «Арсенал»"],
        "Война и мир": ["Романы Льва Толстого", "Романы 1869 года"],
        "Коала": ["Млекопитающие Австралии", "Сумчатые"],
        "Хеди Ламарр": ["Изобретатели США", "Актрисы США"],
    }
    for t, cats in samples.items():
        print(f"{t:20} -> {classify_theme(cats)}")
