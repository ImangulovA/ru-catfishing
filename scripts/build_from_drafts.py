#!/usr/bin/env python3
"""Build day<N>.json files from the hand-authored authoring/drafts.json.

The pool that fed compose_days.py is exhausted (see scripts/REALIA_PIPELINE.md),
so days from MANUAL_FROM onward are written by hand in the browser editor
(scripts/author_server.py). This script is the one-way door between the two
worlds:

    authoring/drafts.json   <- human-readable, committed, edited in the browser
            |
            |  build_from_drafts.py
            v
    app/src/lib/days/day<N>.json   <- hashed/obfuscated, what the game ships

A draft puzzle is plaintext all the way through: the title, every category the
lookup returned, which of those the author hid as too obvious, and the list of
accepted answers. The shipped day is the same thing with `accept` replaced by
sha256(norm(form)) and the title replaced by base64 — exactly what
bulk_build.build_strict emitted, so the game component needs no changes.

Every accepted answer is run through expand_forms() (drops a trailing
qualifier/date) before hashing, the same as the automated path.

Usage:
    python3 build_from_drafts.py             # build every complete draft day
    python3 build_from_drafts.py --day 156   # just one day
    python3 build_from_drafts.py --check     # validate, write nothing
"""
import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys

from make_day import expand_forms, norm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
DRAFTS = os.path.join(ROOT, "authoring", "drafts.json")
DAYS_OUT = os.path.join(ROOT, "app", "src", "lib", "days")

PER_DAY = 10
MIN_CATEGORIES = 4
# Days below this are machine-composed and must never be touched from here.
MANUAL_FROM = 156


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def b64(s):
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def load_drafts():
    if not os.path.exists(DRAFTS):
        return {"version": 1, "days": {}}
    with open(DRAFTS, encoding="utf-8") as fh:
        return json.load(fh)


def visible_categories(p):
    hidden = set(p.get("hidden") or [])
    return [c for c in p.get("categories") or [] if c not in hidden]


def accept_hashes(p):
    """sha256(norm(form)) for every accepted answer, expanded and deduped."""
    forms = set()
    for answer in p.get("accept") or []:
        for f in expand_forms(answer.strip()):
            n = norm(f)
            if n:
                forms.add(n)
    return sorted(sha256(f) for f in forms)


def check_puzzle(p, slot):
    """Return a list of human-readable problems with one draft puzzle."""
    problems = []
    title = (p.get("title") or "").strip()
    if not title:
        return [f"слот {slot}: пустой заголовок"]
    cats = visible_categories(p)
    if len(cats) < MIN_CATEGORIES:
        problems.append(
            f"слот {slot} ({title}): видимых категорий {len(cats)}, нужно >= {MIN_CATEGORIES}")
    # leak: the plaintext title must not appear inside a category shown to the player
    leaks = [c for c in cats if title in c]
    if leaks:
        problems.append(f"слот {slot} ({title}): заголовок виден в категории — {leaks[0]}")
    if not accept_hashes(p):
        problems.append(f"слот {slot} ({title}): нет ни одного зачёта")
    if p.get("difficulty") not in ("easy", "medium", "hard"):
        problems.append(f"слот {slot} ({title}): сложность не задана")
    return problems


def check_day(day_idx, day):
    problems = []
    puzzles = day.get("puzzles") or []
    if len(puzzles) != PER_DAY:
        problems.append(f"загадок {len(puzzles)}, нужно ровно {PER_DAY}")
    seen = {}
    for slot, p in enumerate(puzzles, 1):
        problems += check_puzzle(p, slot)
        title = (p.get("title") or "").strip()
        if title and title in seen:
            problems.append(f"слот {slot}: {title} уже стоит в слоте {seen[title]}")
        elif title:
            seen[title] = slot
    return problems


def build_day(day_idx, day):
    return {
        "day": str(day_idx),
        "puzzles": [
            {
                "categories": visible_categories(p),
                "accept": accept_hashes(p),
                "reveal": b64((p.get("title") or "").strip()),
                "difficulty": p.get("difficulty"),
            }
            for p in day["puzzles"]
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, help="build only this day index")
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    ap.add_argument("--no-index", action="store_true", help="skip gen_index.py")
    args = ap.parse_args()

    drafts = load_drafts()
    days = drafts.get("days") or {}
    wanted = [str(args.day)] if args.day is not None else sorted(days, key=int)

    written, skipped = [], []
    for key in wanted:
        if key not in days:
            print(f"day {key}: нет в черновиках", file=sys.stderr)
            return 1
        idx = int(key)
        if idx < MANUAL_FROM:
            print(f"day {idx}: ниже MANUAL_FROM={MANUAL_FROM}, пропускаю "
                  f"(машинные дни не переписываем)", file=sys.stderr)
            continue
        problems = check_day(idx, days[key])
        if problems:
            skipped.append((idx, problems))
            continue
        if not args.check:
            out = build_day(idx, days[key])
            path = os.path.join(DAYS_OUT, f"day{idx}.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(out, fh, ensure_ascii=False, indent=2)
        written.append(idx)

    for idx, problems in skipped:
        print(f"day {idx}: НЕ ГОТОВ")
        for p in problems:
            print(f"    - {p}")

    verb = "готовы" if args.check else "записаны"
    print(f"\n{verb}: {len(written)} дней" + (f" ({written[0]}..{written[-1]})" if written else ""))
    if skipped:
        print(f"не готовы: {len(skipped)} дней — {[i for i, _ in skipped]}")

    if written and not args.check and not args.no_index:
        subprocess.run([sys.executable, os.path.join(HERE, "gen_index.py")], check=True)
        print("index.js перегенерирован")
    return 0


if __name__ == "__main__":
    sys.exit(main())
