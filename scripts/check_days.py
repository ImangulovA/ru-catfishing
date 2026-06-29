#!/usr/bin/env python3
"""Data-quality gate over every built dayN.json.

Checks, per puzzle: >=4 categories, no per-puzzle leak (title not a substring of
its own categories), valid difficulty tier. Across all days: no duplicate titles
(by norm key). Exits non-zero if any hard check fails.
"""
import base64
import glob
import json
import os
import sys

from make_day import norm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAYS_DIR = os.path.join(ROOT, "app", "src", "lib", "days")
TIERS = {"easy", "medium", "hard"}


def reveal_title(b64):
    return base64.b64decode(b64).decode("utf-8")


def main():
    low = leaks = bad_diff = 0
    seen = {}            # norm-key -> "dayN#idx"
    dups = []
    ndays = npuz = 0
    for f in sorted(glob.glob(os.path.join(DAYS_DIR, "day*.json")),
                    key=lambda p: int(os.path.basename(p)[3:-5])):
        d = json.load(open(f, encoding="utf-8"))
        ndays += 1
        for k, p in enumerate(d.get("puzzles", [])):
            npuz += 1
            title = reveal_title(p["reveal"])
            cats = p.get("categories", [])
            where = f"day{d['day']}#{k}"
            if len(cats) < 4:
                low += 1
                print(f"  LOW  {where} ({len(cats)} cats): {title}", file=sys.stderr)
            if any(title in c for c in cats):
                leaks += 1
                print(f"  LEAK {where}: {title}", file=sys.stderr)
            if p.get("difficulty") not in TIERS:
                bad_diff += 1
                print(f"  DIFF {where}: {p.get('difficulty')!r}", file=sys.stderr)
            key = norm(title)
            if key in seen:
                dups.append(f"{where} == {seen[key]} ({title})")
            else:
                seen[key] = where

    print(f"\ndays={ndays} puzzles={npuz}")
    print(f"low(<4 cats)={low}  leaks={leaks}  bad_difficulty={bad_diff}  dups={len(dups)}")
    for dline in dups[:30]:
        print("  DUP:", dline)
    # leaks + dups are hard failures; low/bad_diff are warnings
    if leaks or dups:
        sys.exit(1)
    print("DQ OK ✅")


if __name__ == "__main__":
    main()
