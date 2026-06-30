#!/usr/bin/env python3
"""Build / inspect the spare-answer pool used for quick puzzle replacements.

A spare = a title that is (a) LLM-proven solvable (in _solvable.json), (b) NOT
used in ANY built day, classified by theme+tier (from _classified.json) and
sorted by pageviews descending (famous first). Output (author-only, gitignored):

  prototype/data/_spares.json
    {"meta": {...}, "buckets": {"theme|tier": [{"title","pv"}, ...]}}

Usage:
  python3 spares.py                  # rebuild _spares.json + print summary table
  python3 spares.py history hard     # list one theme+tier bucket
  python3 spares.py --tier hard      # list every theme's spares for one tier
  python3 spares.py --theme music    # list one theme across all tiers

Run after composing/replacing days so the "used" set stays current.
"""
import base64
import glob
import json
import os
import sys
from collections import defaultdict

from make_day import norm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAYS = os.path.join(ROOT, "app", "src", "lib", "days")
DATA = os.path.join(ROOT, "prototype", "data")
SOLVABLE = os.path.join(DATA, "_solvable.json")
CLASSIFIED = os.path.join(DATA, "_classified.json")
BANNED = os.path.join(DATA, "_banned.json")
OUT = os.path.join(DATA, "_spares.json")
TIERS = ["easy", "medium", "hard"]


def rt(b):
    return base64.b64decode(b).decode("utf-8")


def banned_keys():
    """norm() keys of titles the user explicitly removed -- never offered again."""
    if not os.path.exists(BANNED):
        return set()
    return {norm(t) for t in json.load(open(BANNED, encoding="utf-8"))}


def used_keys():
    keys = set()
    for f in glob.glob(os.path.join(DAYS, "day*.json")):
        d = json.load(open(f, encoding="utf-8"))
        for p in d.get("puzzles", []):
            keys.add(norm(rt(p["reveal"])))
    return keys


def build():
    solv = json.load(open(SOLVABLE, encoding="utf-8"))
    cls = json.load(open(CLASSIFIED, encoding="utf-8"))
    used = used_keys() | banned_keys()
    buckets = defaultdict(list)
    dropped = 0
    for t in solv:
        if norm(t) in used:
            continue
        m = cls.get(t)
        if not m:
            dropped += 1
            continue
        buckets[f"{m['theme']}|{m['tier']}"].append({"title": t, "pv": m.get("pv", 0)})
    for k in buckets:
        buckets[k].sort(key=lambda r: r["pv"], reverse=True)
    total = sum(len(v) for v in buckets.values())
    out = {"meta": {"total": total, "used_days_titles": len(used),
                    "solvable": len(solv), "no_classification_dropped": dropped},
           "buckets": dict(buckets)}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out


def summary(out):
    buckets = out["buckets"]
    themes = sorted({k.split("|")[0] for k in buckets})
    print(f"SPARE POOL: {out['meta']['total']} unused solvable titles "
          f"(of {out['meta']['solvable']} solvable; {out['meta']['used_days_titles']} used)\n")
    print(f"{'theme':<12}" + "".join(f"{t:>9}" for t in TIERS) + f"{'total':>9}")
    col = {t: 0 for t in TIERS}
    for th in themes:
        row = [len(buckets.get(f"{th}|{t}", [])) for t in TIERS]
        for t, c in zip(TIERS, row):
            col[t] += c
        print(f"{th:<12}" + "".join(f"{c:>9}" for c in row) + f"{sum(row):>9}")
    print(f"{'TOTAL':<12}" + "".join(f"{col[t]:>9}" for t in TIERS)
          + f"{out['meta']['total']:>9}")
    print(f"\n-> {OUT}")


def list_bucket(out, theme=None, tier=None):
    buckets = out["buckets"]
    keys = [k for k in sorted(buckets)
            if (theme is None or k.split("|")[0] == theme)
            and (tier is None or k.split("|")[1] == tier)]
    for k in keys:
        print(f"\n# {k}  ({len(buckets[k])})")
        for r in buckets[k]:
            print(f"  {r['pv']:>8}  {r['title']}")


def main():
    out = build()
    args = sys.argv[1:]
    if not args:
        summary(out)
    elif args[0] == "--tier":
        list_bucket(out, tier=args[1])
    elif args[0] == "--theme":
        list_bucket(out, theme=args[1])
    elif len(args) == 2:
        list_bucket(out, theme=args[0], tier=args[1])
    else:
        summary(out)


if __name__ == "__main__":
    main()
