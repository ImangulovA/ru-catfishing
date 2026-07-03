#!/usr/bin/env python3
"""Build the author-only theme+difficulty map over every puzzle title.

Scans app/src/lib/days/day*.json (decoding the base64 reveal -> title, reading
the shipped categories), folds in extra titles from prototype/data/_famous.txt,
classifies THEME, fetches pageviews, scores DIFFICULTY, assigns GLOBAL terciles,
and writes prototype/data/_classified.json = {title: {theme,tier,pv,n_cats}}.

This file holds NO answer hashes, so it is safe to read/inspect.
"""
import base64
import glob
import json
import os
import re
import sys

from classify import (
    assign_tiers,
    classify_theme,
    difficulty_score,
    fetch_pageviews,
    flush_pv_cache,
    PV_FLOOR,
    THEME_LABELS,
)
from build_pool import (fetch_categories, flush_cats_cache, is_giveaway,
                        is_service, title_tokens)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAYS_DIR = os.path.join(ROOT, "app", "src", "lib", "days")
DATA = os.path.join(ROOT, "prototype", "data")
OUT = os.path.join(DATA, "_classified.json")
FAMOUS = os.path.join(DATA, "_famous.txt")
TOP = os.path.join(DATA, "_top_titles.json")
REALIA = os.path.join(DATA, "_realia_titles.json")  # non-person: works/objects/concepts


def reveal_title(b64):
    return base64.b64decode(b64).decode("utf-8")


def gather_from_days():
    """title -> shipped categories (already filtered) for every built day."""
    items = {}
    for f in glob.glob(os.path.join(DAYS_DIR, "day*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        for p in d.get("puzzles", []):
            t = reveal_title(p["reveal"])
            items[t] = p.get("categories", [])
    return items


def useful_cats_for(title):
    cats = fetch_categories(title)
    tokens = title_tokens(re.sub(r"\([^)]*\)", " ", title))
    return sorted(c for c in cats if not is_service(c) and not is_giveaway(c, tokens))


def main():
    items = gather_from_days()
    print(f"titles from built days: {len(items)}", file=sys.stderr)

    if os.path.exists(FAMOUS):
        n_new = 0
        for raw in open(FAMOUS, encoding="utf-8"):
            t = raw.strip()
            if not t or t.startswith("#"):
                continue
            if t not in items:
                items[t] = None  # categories fetched below
                n_new += 1
        print(f"+ famous titles not yet in days: {n_new}", file=sys.stderr)

    if os.path.exists(TOP):
        top = json.load(open(TOP, encoding="utf-8"))
        n_top = 0
        for t in top:
            if t not in items:
                items[t] = None
                n_top += 1
        print(f"+ most-viewed titles not yet seen: {n_top}", file=sys.stderr)

    if os.path.exists(REALIA):
        realia = json.load(open(REALIA, encoding="utf-8"))
        n_re = 0
        for t in realia:
            if t not in items:
                items[t] = None
                n_re += 1
        print(f"+ realia (non-person) titles not yet seen: {n_re}", file=sys.stderr)

    records = {}
    scores = []
    total = len(items)
    for n, (title, cats) in enumerate(items.items(), 1):
        if cats is None:
            try:
                cats = useful_cats_for(title)
            except Exception as e:
                print(f"  cats ERR {title!r}: {e}", file=sys.stderr)
                cats = []
        theme = classify_theme(cats)
        pv = fetch_pageviews(title)
        ncat = len(cats)
        records[title] = {"theme": theme, "pv": round(pv, 1), "n_cats": ncat}
        scores.append((title, difficulty_score(pv, ncat)))
        if n % 50 == 0:
            print(f"  classified {n}/{total}", file=sys.stderr)
            json.dump(records, open(OUT, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)

    # Tiers are terciles among PLAYABLE (famous) titles only: pv >= floor AND
    # >= 4 categories. Everything below the fame floor is too obscure to be a
    # candidate -> labelled "hard" for display, excluded from composition by pv.
    survivors = [(t, sc) for (t, sc) in scores
                 if records[t]["pv"] >= PV_FLOOR and records[t]["n_cats"] >= 4]
    tiers = assign_tiers(survivors)
    for title in records:
        records[title]["tier"] = tiers.get(title, "hard")

    flush_pv_cache()
    flush_cats_cache()
    json.dump(records, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # summary
    from collections import Counter
    th = Counter(r["theme"] for r in records.values())
    ti = Counter(tiers.values())
    print(f"\nwrote {len(records)} -> {OUT}")
    print(f"playable (pv>={PV_FLOOR}, >=4 cats): {len(survivors)} of {len(records)}")
    print("playable themes:",
          {THEME_LABELS[k]: v for k, v in
           Counter(records[t]["theme"] for t, _ in survivors).most_common()})
    print("playable tiers :", dict(ti))


if __name__ == "__main__":
    main()
