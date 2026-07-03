#!/usr/bin/env python3
"""Prepare ONLY the new realia for the LLM solvability screen (people are already
screened in _solvable.json; don't re-screen them).

Candidates = titles in _realia_titles.json that are classified, pv >= REALIA_FLOOR,
>= 4 filtered cats, not excluded, not locked (days <=25), and NOT already solvable.
Writes:
  /tmp/screen_realia/map.json      [{id, title, theme, tier}]  (answer key, local)
  /tmp/screen_realia/batch_NNN.txt lines "id TAB cat | cat ..."  (NO titles -> swarm)
Categories come from the on-disk cats cache (warmed by classify_pool) -> no network.
"""
import base64
import glob
import json
import os
import re

from make_day import norm
from classify import is_excluded
from build_pool import fetch_categories, is_giveaway, is_service, title_tokens

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAYS = os.path.join(ROOT, "app", "src", "lib", "days")
DATA = os.path.join(ROOT, "prototype", "data")
CLASSIFIED = os.path.join(DATA, "_classified.json")
REALIA = os.path.join(DATA, "_realia_titles.json")
SOLVABLE = os.path.join(DATA, "_solvable.json")
OUT = "/tmp/screen_realia"
LOCKED_MAX = 25
BATCH = 20
REALIA_FLOOR = 3000


def rt(b):
    return base64.b64decode(b).decode("utf-8")


def locked_keys():
    locked = set()
    for f in glob.glob(os.path.join(DAYS, "day*.json")):
        try:
            n = int(os.path.basename(f)[3:-5])
        except ValueError:
            continue
        if n > LOCKED_MAX:
            continue
        d = json.load(open(f, encoding="utf-8"))
        for p in d.get("puzzles", []):
            locked.add(norm(rt(p["reveal"])))
    return locked


def useful_cats(title):
    cats = fetch_categories(title)
    tokens = title_tokens(re.sub(r"\([^)]*\)", " ", title))
    return sorted(c for c in cats if not is_service(c) and not is_giveaway(c, tokens))


def main():
    os.makedirs(OUT, exist_ok=True)
    cls = json.load(open(CLASSIFIED, encoding="utf-8"))
    realia = json.load(open(REALIA, encoding="utf-8"))
    already = {norm(t) for t in json.load(open(SOLVABLE, encoding="utf-8"))} \
        if os.path.exists(SOLVABLE) else set()
    locked = locked_keys()

    rows, seen = [], set()
    for t in realia:
        m = cls.get(t)
        if not m or m.get("pv", 0) < REALIA_FLOOR or m.get("n_cats", 0) < 4:
            continue
        k = norm(t)
        if k in seen or k in already or k in locked:
            continue
        try:
            cats = useful_cats(t)
        except Exception as e:
            print(f"  cats ERR {t!r}: {e}")
            continue
        if len(cats) < 4 or is_excluded(cats):
            continue
        seen.add(k)
        rows.append({"id": len(rows), "title": t, "theme": m["theme"],
                     "tier": m["tier"], "cats": cats})

    json.dump(rows, open(os.path.join(OUT, "map.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    nb = 0
    for b in range(0, len(rows), BATCH):
        with open(os.path.join(OUT, f"batch_{nb:03}.txt"), "w", encoding="utf-8") as f:
            for r in rows[b:b + BATCH]:
                f.write(f"{r['id']}\t" + " | ".join(r["cats"]) + "\n")
        nb += 1
    print(f"wrote {len(rows)} realia candidates in {nb} batch files -> {OUT}")


if __name__ == "__main__":
    main()
