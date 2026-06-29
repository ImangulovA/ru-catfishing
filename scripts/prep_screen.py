#!/usr/bin/env python3
"""Prepare the famous candidate pool for the LLM solvability screen.

For every playable candidate (pv>=5000, >=4 cats, not excluded, not locked) we
need its FILTERED categories. Candidates already present in a built day reuse the
shipped categories; the rest are fetched. We then write:
  /tmp/screen/map.json        [{id, title, theme, tier}]  (answer key, local-only)
  /tmp/screen/batch_NNN.txt   lines "id TAB cat | cat ..."  (NO titles -> swarm)
The swarm reads batch files and returns {id: guess}; verify_screen.py checks them.
"""
import base64
import glob
import json
import os
import re
import sys

from make_day import norm
from classify import PV_FLOOR, is_excluded
from build_pool import fetch_categories, is_giveaway, is_service, title_tokens

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAYS = os.path.join(ROOT, "app", "src", "lib", "days")
DATA = os.path.join(ROOT, "prototype", "data")
CLASSIFIED = os.path.join(DATA, "_classified.json")
OUT = "/tmp/screen"
LOCKED_MAX = 25
BATCH = 20


def rt(b):
    return base64.b64decode(b).decode("utf-8")


def day_cats_index():
    """title -> categories from all built day files (free, no network)."""
    idx, locked = {}, set()
    for f in glob.glob(os.path.join(DAYS, "day*.json")):
        try:
            n = int(os.path.basename(f)[3:-5])
        except ValueError:
            continue
        d = json.load(open(f, encoding="utf-8"))
        for p in d.get("puzzles", []):
            t = rt(p["reveal"])
            idx[t] = p.get("categories", [])
            if n <= LOCKED_MAX:
                locked.add(norm(t))
    return idx, locked


def useful_cats(title):
    cats = fetch_categories(title)
    tokens = title_tokens(re.sub(r"\([^)]*\)", " ", title))
    return sorted(c for c in cats if not is_service(c) and not is_giveaway(c, tokens))


def main():
    os.makedirs(OUT, exist_ok=True)
    cls = json.load(open(CLASSIFIED, encoding="utf-8"))
    have, locked = day_cats_index()
    cands = [(t, m) for t, m in cls.items()
             if m.get("pv", 0) >= PV_FLOOR and m.get("n_cats", 0) >= 4
             and norm(t) not in locked]
    print(f"{len(cands)} candidates; fetching cats for spares...", file=sys.stderr)

    rows = []
    seen = set()
    for i, (t, m) in enumerate(cands):
        if norm(t) in seen:
            continue
        cats = have.get(t)
        if cats is None:
            try:
                cats = useful_cats(t)
            except Exception as e:
                print(f"  cats ERR {t!r}: {e}", file=sys.stderr)
                continue
        if len(cats) < 4 or is_excluded(cats):
            continue
        seen.add(norm(t))
        rows.append({"id": len(rows), "title": t, "theme": m["theme"],
                     "tier": m["tier"], "cats": cats})
        if (i + 1) % 200 == 0:
            print(f"  {i + 1}/{len(cands)} processed, {len(rows)} kept", file=sys.stderr)

    json.dump(rows, open(os.path.join(OUT, "map.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    nb = 0
    for b in range(0, len(rows), BATCH):
        chunk = rows[b:b + BATCH]
        with open(os.path.join(OUT, f"batch_{nb:03}.txt"), "w", encoding="utf-8") as f:
            for r in chunk:
                f.write(f"{r['id']}\t" + " | ".join(r["cats"]) + "\n")
        nb += 1
    print(f"wrote {len(rows)} candidates in {nb} batch files -> {OUT}")


if __name__ == "__main__":
    main()
