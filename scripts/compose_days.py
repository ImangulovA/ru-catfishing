#!/usr/bin/env python3
"""Compose balanced future days (>= START) from a classified candidate pool.

Inputs:
  prototype/data/_classified.json  (theme + GLOBAL tier per title; classify_pool.py)
  existing day*.json               (candidate titles from days 26.. + locked -1..25)
  prototype/data/_famous.txt       (curated well-known titles, optional)

Rules per day (10 puzzles):
  - difficulty curve  3 easy / 4 medium / 3 hard
  - theme quota       max 2 of one theme, aim >= 5 distinct themes
  - theme spread      least-recently-used theme preferred across the horizon
  - intra-day order   deterministic shuffle, no long runs of the same tier
Locked titles (days -1..25) are never reused; candidates are deduped by norm().

Each chosen title is rebuilt with build_strict() (current norm + qualifier
expansion + difficulty), so the shipped hashes are fresh. Titles that fail the
quality gate (<4 cats / military / leak) are skipped and back-filled.
"""
import argparse
import base64
import glob
import json
import os
import random
import sys
import time
from collections import Counter

from classify import PV_FLOOR, THEME_LABELS, is_excluded
from make_day import norm
from bulk_build import build_strict, write_day

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAYS_DIR = os.path.join(ROOT, "app", "src", "lib", "days")
DATA = os.path.join(ROOT, "prototype", "data")
CLASSIFIED = os.path.join(DATA, "_classified.json")
FAMOUS = os.path.join(DATA, "_famous.txt")

LOCKED_MAX = 29     # days -1..29 are released/locked (day0 = 2026-06-04)
CURVE = [("easy", 3), ("medium", 4), ("hard", 3)]
PER_DAY = 10
DEFAULT_CAP = 2     # max puzzles of one theme per day
THEME_CAP = {"sport": 1}    # sport must not repeat in a day (no 2 footballers)
PERSON_CAP = 5      # max puzzles about a person per day (rest are "realia")
REALIA_FLOOR = 2000  # realia are famous enough lower than people (people: PV_FLOOR)

_CATS_CACHE = os.path.join(DATA, "_cats_cache.json")
_REALIA = os.path.join(DATA, "_realia_titles.json")


def cap_for(theme):
    return THEME_CAP.get(theme, DEFAULT_CAP)


def load_realia():
    if os.path.exists(_REALIA):
        return {dedup_key(t) for t in json.load(open(_REALIA, encoding="utf-8"))}
    return set()


def build_person_map():
    """title-key -> is_person, from day-file categories + the cats cache. A person
    is any article with a birth/death-year category (Родивш*/Умерш*)."""
    cats_by_title = {}
    if os.path.exists(_CATS_CACHE):
        cats_by_title.update(json.load(open(_CATS_CACHE, encoding="utf-8")))
    for f in glob.glob(os.path.join(DAYS_DIR, "day*.json")):
        d = json.load(open(f, encoding="utf-8"))
        for p in d.get("puzzles", []):
            cats_by_title[reveal_title(p["reveal"])] = p.get("categories", [])
    person = {}
    for t, cats in cats_by_title.items():
        person[dedup_key(t)] = any("Родивш" in c or "Умерш" in c for c in (cats or []))
    return person


def reveal_title(b64):
    return base64.b64decode(b64).decode("utf-8")


def dedup_key(title):
    return norm(title)


def gather_locked_keys(upto):
    """Lock (never reuse) every title in a day we are KEEPING, i.e. any day index
    below `upto` (the recompose start). Guarantees no dups vs preserved days."""
    keys = set()
    for f in glob.glob(os.path.join(DAYS_DIR, "day*.json")):
        try:
            n = int(os.path.basename(f)[3:-5])
        except ValueError:
            continue
        if n >= upto:
            continue
        d = json.load(open(f, encoding="utf-8"))
        for p in d.get("puzzles", []):
            keys.add(dedup_key(reveal_title(p["reveal"])))
    return keys


def arrange_no_runs(day, rng):
    """Interleave the 10 puzzles so difficulty is shuffled, never sorted, and
    avoids 3-of-the-same-tier in a row whenever feasible."""
    from collections import defaultdict
    buckets = defaultdict(list)
    items = day[:]
    rng.shuffle(items)
    for it in items:
        buckets[it["tier"]].append(it)
    result = []
    while len(result) < len(items):
        avail = [t for t in buckets if buckets[t]]

        def no_run(t):
            return not (len(result) >= 2 and result[-1]["tier"] == t == result[-2]["tier"])

        choices = [t for t in avail if no_run(t)] or avail
        # spread: prefer the tier with the most remaining, random tie-break
        choices.sort(key=lambda t: (-len(buckets[t]), rng.random()))
        result.append(buckets[choices[0]].pop())
    return result


def compose(pool, seed):
    """Greedy pack pool -> list of days (each a list of {title,theme,tier})."""
    by_tier = {"easy": [], "medium": [], "hard": []}
    for p in pool:
        by_tier.get(p["tier"], by_tier["medium"]).append(p)
    rng = random.Random(seed)
    for k in by_tier:
        rng.shuffle(by_tier[k])

    theme_last = {k: -1 for k in THEME_LABELS}
    days = []
    round_i = 0

    def ok_person(c, day_people):
        return not (c.get("person") and day_people >= PERSON_CAP)

    def take(tier, day_themes, day_people):
        # prefer least-recently-used theme that is under its per-day cap
        for th in sorted(THEME_LABELS, key=lambda t: theme_last[t]):
            if day_themes.get(th, 0) >= cap_for(th):
                continue
            for idx, c in enumerate(by_tier[tier]):
                if c["theme"] == th and ok_person(c, day_people):
                    return by_tier[tier].pop(idx)
        # relax: any candidate of this tier whose theme isn't capped (never
        # exceed a cap — sport=1 and the person cap must hold as a last resort)
        for idx, c in enumerate(by_tier[tier]):
            if day_themes.get(c["theme"], 0) < cap_for(c["theme"]) and ok_person(c, day_people):
                return by_tier[tier].pop(idx)
        return None

    def take_relaxed(tier, day_themes, relaxed, day_people):
        nearest = {
            "easy": ["easy", "medium", "hard"],
            "medium": ["medium", "easy", "hard"],
            "hard": ["hard", "medium", "easy"],
        }[tier]
        for tt in nearest:
            c = take(tt, day_themes, day_people)
            if c:
                if tt != tier:
                    relaxed[0] += 1
                return c
        return None

    relaxed = [0]
    # stop before the pool degenerates into a single-tier "dregs" day: require a
    # minimum mix of each tier so every emitted day stays shuffleable.
    while (sum(len(v) for v in by_tier.values()) >= PER_DAY
           and all(len(by_tier[t]) >= 2 for t in ("easy", "medium", "hard"))):
        day, day_themes, day_people = [], {}, 0
        for tier, count in CURVE:
            for _ in range(count):
                c = take_relaxed(tier, day_themes, relaxed, day_people)
                if c is None:
                    break
                day.append(c)
                day_themes[c["theme"]] = day_themes.get(c["theme"], 0) + 1
                if c.get("person"):
                    day_people += 1
        if len(day) < PER_DAY:
            break
        for c in day:
            theme_last[c["theme"]] = round_i
        days.append(arrange_no_runs(day, rng))
        round_i += 1
    return days, relaxed[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=26)
    ap.add_argument("--max-days", type=int, default=0, help="0 = as many as pool allows")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sleep", type=float, default=0.3, help="polite pause between builds")
    args = ap.parse_args()

    cls = json.load(open(CLASSIFIED, encoding="utf-8"))
    locked = gather_locked_keys(args.start)
    banned_path = os.path.join(DATA, "_banned.json")
    if os.path.exists(banned_path):
        banned = {dedup_key(t) for t in json.load(open(banned_path, encoding="utf-8"))}
        locked |= banned  # never re-offer titles the user explicitly removed
        print(f"banned filter: {len(banned)} titles", file=sys.stderr)
    realia = load_realia()          # dedup keys of non-person "вещи"
    person_map = build_person_map()  # dedup key -> is_person
    # solvable filter: if the screen has run, only LLM-solvable titles qualify
    solv_path = os.path.join(DATA, "_solvable.json")
    solvable = None
    if os.path.exists(solv_path):
        solvable = {dedup_key(t) for t in json.load(open(solv_path, encoding="utf-8"))}
        print(f"solvable filter: {len(solvable)} titles", file=sys.stderr)
    # candidates = famous enough (realia at a lower floor) & detailed & solvable &
    # not released, deduped
    pool = []
    seen = set()
    for t, meta in cls.items():
        k = dedup_key(t)
        floor = REALIA_FLOOR if k in realia else PV_FLOOR
        if meta.get("pv", 0) < floor or meta.get("n_cats", 0) < 4:
            continue
        if k in locked or k in seen:
            continue
        if solvable is not None and k not in solvable:
            continue
        seen.add(k)
        pool.append({"title": t, "theme": meta["theme"], "tier": meta["tier"],
                     "person": person_map.get(k, False)})
    n_people = sum(1 for p in pool if p["person"])
    print(f"locked={len(locked)} candidates={len(pool)} "
          f"(people={n_people}, realia_floor={REALIA_FLOOR}, person_cap={PERSON_CAP}/day) "
          f"(tiers={Counter(p['tier'] for p in pool)})", file=sys.stderr)

    days, relaxed = compose(pool, args.seed)
    if args.max_days:
        days = days[: args.max_days]
    print(f"composed {len(days)} days (slot relaxations: {relaxed})", file=sys.stderr)

    # Candidates are already gathered + classified, so it is now safe to remove
    # every existing future day (>= start): any day index NOT rewritten below
    # would otherwise linger with stale-norm hashes and a broken answer check.
    removed = 0
    for f in glob.glob(os.path.join(DAYS_DIR, "day*.json")):
        try:
            n = int(os.path.basename(f)[3:-5])
        except ValueError:
            continue
        if n >= args.start:
            os.remove(f)
            removed += 1
    print(f"removed {removed} stale future day files (>= {args.start})", file=sys.stderr)

    # build + write each day; back-fill any title that fails build_strict
    leftover = []  # spare pool drained for back-fill (any tier)
    seen_titles = set()
    for day in days:
        for c in day:
            seen_titles.add(c["title"])
    # spares = classified candidates not used in any composed day
    for p in pool:
        if p["title"] not in seen_titles:
            leftover.append(p)

    def take_spare(tier, day_themes, day_people):
        def usable(sp):
            return (day_themes.get(sp["theme"], 0) < cap_for(sp["theme"])
                    and not (sp.get("person") and day_people >= PERSON_CAP))
        # prefer same tier whose theme + person cap are still ok
        for i, sp in enumerate(leftover):
            if sp["tier"] == tier and usable(sp):
                return leftover.pop(i)
        for i, sp in enumerate(leftover):
            if usable(sp):
                return leftover.pop(i)
        return None

    built = 0
    for d, day in enumerate(days):
        idx = args.start + d
        puzzles = []
        used_keys = set()
        day_themes = {}
        day_people = 0
        queue = list(day)
        while queue and len(puzzles) < PER_DAY:
            c = queue.pop(0)
            # theme-cap (sport=1) / person-cap guard: if the day is already at the
            # cap for this theme or for people, swap for a balance-safe spare
            over_theme = day_themes.get(c["theme"], 0) >= cap_for(c["theme"])
            over_people = c.get("person") and day_people >= PERSON_CAP
            if over_theme or over_people:
                repl = take_spare(c["tier"], day_themes, day_people)
                if repl:
                    queue.append(repl)
                print(f"  day{idx} cap {'people' if over_people else c['theme']}: "
                      f"{c['title']!r} -> {repl['title'] if repl else 'NO SPARE'}",
                      file=sys.stderr)
                continue
            try:
                strict, n, status = build_strict(c["title"], c["tier"])
            except Exception as e:
                status = "err"
                print(f"  day{idx} ERR {c['title']!r}: {e}", file=sys.stderr)
            time.sleep(args.sleep)
            excl = is_excluded(strict["categories"]) if status == "ok" else None
            if status == "ok" and not excl:
                k = dedup_key(c["title"])
                if k in used_keys:
                    continue
                used_keys.add(k)
                puzzles.append({"title": c["title"], "strict": strict})
                day_themes[c["theme"]] = day_themes.get(c["theme"], 0) + 1
                if c.get("person"):
                    day_people += 1
            else:
                repl = take_spare(c["tier"], day_themes, day_people)
                if repl:
                    queue.append(repl)
                print(f"  day{idx} skip {excl or status}: {c['title']!r} "
                      f"-> {repl['title'] if repl else 'NO SPARE'}", file=sys.stderr)
        if len(puzzles) == PER_DAY:
            write_day(idx, puzzles)
            built += 1
            tiers = Counter(p["strict"]["difficulty"] for p in puzzles)
            print(f"[day {idx}] {dict(tiers)}")
        else:
            print(f"[day {idx}] INCOMPLETE ({len(puzzles)}/10) — stopping", file=sys.stderr)
            break

    print(f"\nDONE: built days {args.start}..{args.start + built - 1} ({built} days)")


if __name__ == "__main__":
    main()
