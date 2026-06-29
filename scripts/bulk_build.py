#!/usr/bin/env python3
"""Bulk-build many days of ru-catfishing puzzles straight from ru.wiki.

Source = the FULL Featured ("Избранные") + Good ("Хорошие") article lists. We
shuffle them (fixed seed, so runs are reproducible / resumable), then for each
candidate do the FULL strict build (categories + filter + surname + en langlink
+ redirect aliases) in a single pass. Candidates that fail a quality gate are
skipped:
  - low : < MIN_CATEGORIES useful categories after filtering (incl. disambig=0)
  - mil : military HARDWARE (a weapon / vehicle / warship / aircraft) — but a
          PERSON/event with a military category is kept (Навратилова стоп-фолс)
  - leak: the plaintext title appears inside one of its own categories
  - dup : already used by an existing day, or already taken this run

Good puzzles are packed 10-per-day starting at START_DAY. Each day's strict json
is written as soon as it fills, and progress is checkpointed so the run resumes.

Usage:
    python3 bulk_build.py --days 100              # build 100 days from START_DAY
    python3 bulk_build.py --days 2 --start 24     # small smoke test
"""
import argparse
import base64
import hashlib
import json
import os
import random
import re
import sys
import time

from build_pool import (
    SEED_CATEGORIES,
    api_get,
    fetch_categories,
    fetch_langlink,
    fetch_redirects,
    is_giveaway,
    is_service,
    title_tokens,
)
from make_day import derive_surname, expand_forms, given_surname_form, norm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "prototype", "data")
DAYS_OUT = os.path.join(ROOT, "app", "src", "lib", "days")
PER_DAY = 10
MIN_CATEGORIES = 4

# Military-HARDWARE category/title markers. Only excludes when the article is NOT
# a person/event (see is_military), so biographies that merely touch the military
# (pilots, generals, plane-crash victims) are kept.
MIL_MARKERS = [
    "танк", "пушка", "гаубиц", "миномёт", "миномет", "пулемёт", "пулемет",
    "винтовк", "пистолет", "орудие", "артиллери", "бронеавтомоб",
    "бронетранспорт", "боевая машина", "боевые машины", "крейсер", "линкор",
    "линейный корабл", "эсминец", "миноносец", "подводная лодка",
    "подводные лодки", "истребител", "бомбардировщик", "штурмовик",
    "военная техника", "торпед", "снаряд (", "патрон", "авианос",
    "канонерск", "фрегат", "корвет", "дредноут", "самоходн", "гранатомёт",
    "гранатомет", "боеприпас", "стрелковое оруж", "холодное оруж",
    "баллистическая ракета", "крылатая ракета", "зенитн", "ракетный комплекс",
    "ракетный корабл", "ракетный катер", "военные самол", "военный самол",
]
PERSON_MARKERS = ["родивш", "умерш", "персоналии"]


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def b64(s):
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def fetch_all_titles():
    """Full Featured + Good article title lists (cached to disk)."""
    cache = os.path.join(DATA, "_seed_titles.json")
    if os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    titles = []
    for cat in SEED_CATEGORIES:
        cont = None
        while True:
            params = {
                "action": "query", "list": "categorymembers",
                "cmtitle": cat, "cmnamespace": "0", "cmlimit": "500",
            }
            if cont:
                params["cmcontinue"] = cont
            data = api_get(params)
            titles += [m["title"] for m in data["query"]["categorymembers"]]
            cont = data.get("continue", {}).get("cmcontinue")
            if not cont:
                break
            time.sleep(0.1)
    titles = sorted(set(titles))
    json.dump(titles, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"fetched {len(titles)} seed titles -> {cache}", file=sys.stderr)
    return titles


def is_military(title, cats):
    text = " · ".join(cats).lower()
    t = title.lower()
    is_person = any(any(pm in c.lower() for pm in PERSON_MARKERS) for c in cats)
    if is_person:
        return False
    return any(m in text or m in t for m in MIL_MARKERS)


def build_strict(title, difficulty="medium"):
    """Return (strict_dict | None, n_cats, status)."""
    cats = fetch_categories(title)
    tokens = title_tokens(re.sub(r"\([^)]*\)", " ", title))
    useful = sorted(c for c in cats if not is_service(c) and not is_giveaway(c, tokens))
    if len(useful) < MIN_CATEGORIES:
        return None, len(useful), "low"
    if is_military(title, useful):
        return None, len(useful), "mil"

    # Collect every RAW accepted name, each expanded to its short form, then
    # norm() them all (keeps make_day.py and bulk_build.py in lockstep).
    raws = set(expand_forms(title))
    en = fetch_langlink(title, "en")
    if en:
        raws |= expand_forms(en)
    for red in fetch_redirects(title):
        raws |= expand_forms(red)
    forms = {norm(r) for r in raws}
    sn = derive_surname(title, useful)
    if sn:
        forms.add(norm(sn))
    if en:
        en_sn = derive_surname(en, useful)
        if en_sn:
            forms.add(norm(en_sn))
    gsf = given_surname_form(title, useful)
    if gsf:
        forms.add(norm(gsf))
    forms.discard("")

    strict = {
        "categories": useful,
        "accept": sorted(sha256(f) for f in forms),
        "reveal": b64(title),
        "difficulty": difficulty,
    }
    # per-puzzle leak: plaintext title must not appear inside its own categories
    if any(title in c for c in useful):
        return None, len(useful), "leak"
    return strict, len(useful), "ok"


def write_day(day_idx, puzzles):
    out = {"day": str(day_idx), "puzzles": [p["strict"] for p in puzzles]}
    path = os.path.join(DAYS_OUT, f"day{day_idx}.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    # also a txt record (titles only) for reproducibility / later hand-tweaks
    rec = [f"day: {day_idx}"] + [p["title"] for p in puzzles]
    open(os.path.join(DATA, f"day{day_idx}.txt"), "w", encoding="utf-8").write(
        "\n".join(rec) + "\n"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=100)
    ap.add_argument("--start", type=int, default=24)
    ap.add_argument("--sleep", type=float, default=0.35)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    titles = fetch_all_titles()
    used = set()
    used_path = os.path.join(DATA, "_used_titles.txt")
    if os.path.exists(used_path):
        used = set(open(used_path, encoding="utf-8").read().splitlines())

    candidates = [t for t in titles if t not in used]
    random.seed(args.seed)
    random.shuffle(candidates)

    need = args.days * PER_DAY
    prog_path = os.path.join(DATA, "_bulk_progress.json")
    good = []           # [{title, strict}]
    consumed = set()    # candidate titles already tried (ok or skipped)
    if os.path.exists(prog_path):
        prog = json.load(open(prog_path, encoding="utf-8"))
        good = prog["good"]
        consumed = set(prog["consumed"])
        print(f"resume: {len(good)} good, {len(consumed)} consumed", file=sys.stderr)

    counts = {"ok": len(good), "low": 0, "mil": 0, "leak": 0, "err": 0}
    for title in candidates:
        if len(good) >= need:
            break
        if title in consumed:
            continue
        consumed.add(title)
        try:
            strict, n, status = build_strict(title)
        except Exception as e:
            counts["err"] += 1
            print(f"  ERR {title!r}: {e}", file=sys.stderr)
            time.sleep(args.sleep)
            continue
        counts[status] += 1
        if status == "ok":
            good.append({"title": title, "strict": strict})
            print(f"[{len(good):4}/{need}] +{n:2}c  {title}")
        else:
            print(f"        -{status} ({n}c)  {title}", file=sys.stderr)
        # checkpoint + flush full days every 10 good
        if len(good) % 10 == 0 or len(good) >= need:
            json.dump({"good": good, "consumed": sorted(consumed)},
                      open(prog_path, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(args.sleep)

    # pack good into days
    full = len(good) // PER_DAY
    for d in range(full):
        chunk = good[d * PER_DAY:(d + 1) * PER_DAY]
        write_day(args.start + d, chunk)
    json.dump({"good": good, "consumed": sorted(consumed)},
              open(prog_path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\nDONE: {len(good)} good puzzles -> days "
          f"{args.start}..{args.start + full - 1} ({full} days)")
    print("counts:", counts)


if __name__ == "__main__":
    main()
