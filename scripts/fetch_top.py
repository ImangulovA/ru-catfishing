#!/usr/bin/env python3
"""Aggregate the most-viewed ru.wikipedia articles into a candidate title pool.

The Featured/Good pool skews obscure, so to get GENUINELY well-known puzzles we
pull the Wikimedia "top" pageviews list (top ~1000 articles/day) for one day per
month across a year, union them, and drop non-article junk (namespaces, the main
page, lists, plain dates). Result -> prototype/data/_top_titles.json (plaintext,
author-only). classify_pool.py folds these in; the pv>=floor gate keeps only the
famous ones, and the usual gates (>=4 cats / not disambig / not military) apply
when each chosen title is finally built.
"""
import json
import os
import re
import sys
import time
import urllib.request

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "prototype", "data")
OUT = os.path.join(DATA, "_top_titles.json")
UA = "game-designer/0.1 (personal project; imangulovamal@gmail.com)"

# One sample day (15th) per month over a fixed 12-month window (reproducible).
MONTHS = [
    ("2025", "07"), ("2025", "08"), ("2025", "09"), ("2025", "10"),
    ("2025", "11"), ("2025", "12"), ("2026", "01"), ("2026", "02"),
    ("2026", "03"), ("2026", "04"), ("2026", "05"), ("2026", "06"),
]

# Obvious non-puzzle junk to skip even before the pv/category gates.
SKIP_PREFIX = ("Список", "Служебная", "Special", "Категория", "Шаблон",
               "Википедия", "Портал", "Файл")
SKIP_EXACT = {"Заглавная страница"}


def is_junk(title):
    if title in SKIP_EXACT:
        return True
    if ":" in title:                       # namespaces / "Служебная:..."
        return True
    if any(title.startswith(p) for p in SKIP_PREFIX):
        return True
    if re.fullmatch(r"[\d\W]+", title):    # pure numbers / punctuation
        return True
    return False


def get_top(year, month, day="15"):
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
           f"ru.wikipedia/all-access/{year}/{month}/{day}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    return data.get("items", [{}])[0].get("articles", [])


def main():
    seen = {}
    for (y, m) in MONTHS:
        try:
            arts = get_top(y, m)
        except Exception as e:
            print(f"  {y}-{m}: ERR {e}", file=sys.stderr)
            continue
        kept = 0
        for it in arts:
            title = it.get("article", "").replace("_", " ").strip()
            if not title or is_junk(title):
                continue
            seen[title] = max(seen.get(title, 0), it.get("views", 0))
            kept += 1
        print(f"  {y}-{m}: {kept} kept (total unique {len(seen)})", file=sys.stderr)
        time.sleep(0.2)

    titles = sorted(seen)
    json.dump(titles, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"wrote {len(titles)} most-viewed titles -> {OUT}")


if __name__ == "__main__":
    main()
