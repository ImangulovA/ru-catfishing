#!/usr/bin/env python3
"""Quick puzzle replacement in a future day.

Drive this when the user, while playtesting, says: "in day N remove answer X
(and Y)". For each title to remove we:
  1. locate the puzzle in day N by norm()-match (exact, else substring) on the
     decoded reveal;
  2. pick a SOLVABLE, unused spare of the SAME tier (from _spares.json) -- same
     theme first; if that bucket is empty, the day's least-used theme that keeps
     the balance rules (<=2 per theme, <=1 sport, >=5 distinct themes);
  3. rebuild it with build_strict (fresh categories + answer hashes) and swap it
     into the day at the same index.

Tier is preserved so the 3 easy / 4 medium / 3 hard curve never breaks. Spares
already used in any day are skipped (no cross-day dups). Run check_days.py +
npm build afterwards; this script does a light inline sanity print only.

Usage:
  python3 quick_replace.py N "Title A" "Title B"
  python3 quick_replace.py N "Title A=science"        # force replacement theme
  python3 quick_replace.py N "Title A>Конкретный ответ" # force exact replacement
  python3 quick_replace.py N --dry "Title A"           # preview, do not write
"""
import base64
import glob
import hashlib
import json
import os
import sys
from collections import Counter

from make_day import norm
from bulk_build import build_strict
from classify import is_excluded

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAYS = os.path.join(ROOT, "app", "src", "lib", "days")
DATA = os.path.join(ROOT, "prototype", "data")
SPARES = os.path.join(DATA, "_spares.json")
CLASSIFIED = os.path.join(DATA, "_classified.json")
BANNED = os.path.join(DATA, "_banned.json")
SPORT_CAP = 1
THEME_CAP = 2
MIN_THEMES = 5


def rt(b):
    return base64.b64decode(b).decode("utf-8")


def h(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def day_path(n):
    return os.path.join(DAYS, f"day{n}.json")


def all_used_keys():
    keys = set()
    for f in glob.glob(os.path.join(DAYS, "day*.json")):
        d = json.load(open(f, encoding="utf-8"))
        for p in d.get("puzzles", []):
            keys.add(norm(rt(p["reveal"])))
    return keys


def load_banned():
    if os.path.exists(BANNED):
        return json.load(open(BANNED, encoding="utf-8"))
    return []


def add_banned(titles):
    """Persist removed titles so they're never offered as spares again."""
    cur = load_banned()
    seen = {norm(t) for t in cur}
    for t in titles:
        if norm(t) not in seen:
            cur.append(t)
            seen.add(norm(t))
    json.dump(sorted(cur), open(BANNED, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def theme_of(cls, title):
    return cls.get(title, {}).get("theme", "society")


def find_idx(puzzles, query):
    """Index of the puzzle whose decoded title matches query (norm exact first,
    then substring). Returns (idx, title) or (None, candidates)."""
    titles = [rt(p["reveal"]) for p in puzzles]
    nq = norm(query)
    for i, t in enumerate(titles):
        if norm(t) == nq:
            return i, t
    hits = [(i, t) for i, t in enumerate(titles) if nq in norm(t) or query.lower() in t.lower()]
    if len(hits) == 1:
        return hits[0]
    return None, [t for _i, t in hits] or titles


def pick_spare(spares, used, tier, want_theme, day_theme_counts, forced_theme=None):
    """Return (theme, title) for a same-tier spare, or None. Prefers want_theme,
    else the day's least-used theme that respects caps."""
    def bucket(theme):
        return [r["title"] for r in spares.get(f"{theme}|{tier}", [])
                if norm(r["title"]) not in used]

    order = []
    if forced_theme:
        order = [forced_theme]
    else:
        # same theme first (always balance-safe: we removed one of this theme)
        if bucket(want_theme):
            order.append(want_theme)
        # then other themes by current day count asc (boost diversity), capped
        others = sorted({k.split("|")[0] for k in spares},
                        key=lambda th: day_theme_counts.get(th, 0))
        order += [th for th in others if th != want_theme]

    for theme in order:
        cap = SPORT_CAP if theme == "sport" else THEME_CAP
        # count if we ADD this theme and REMOVED want_theme
        projected = day_theme_counts.get(theme, 0) + (0 if theme == want_theme else 1)
        if theme != want_theme and projected > cap:
            continue
        for title in bucket(theme):
            return theme, title
    return None


def main():
    args = sys.argv[1:]
    dry = "--dry" in args
    args = [a for a in args if a != "--dry"]
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    n = int(args[0])
    requests = args[1:]

    spares = json.load(open(SPARES, encoding="utf-8"))["buckets"]
    cls = json.load(open(CLASSIFIED, encoding="utf-8"))
    d = json.load(open(day_path(n), encoding="utf-8"))
    puzzles = d["puzzles"]
    used = all_used_keys() | {norm(t) for t in load_banned()}
    day_theme_counts = Counter(theme_of(cls, rt(p["reveal"])) for p in puzzles)

    plan = []
    for req in requests:
        forced_theme = forced_title = None
        if "=" in req:
            req, forced_theme = req.split("=", 1)
        if ">" in req:
            req, forced_title = req.split(">", 1)
        idx, found = find_idx(puzzles, req.strip())
        if idx is None:
            print(f"!! '{req}' -> {'AMBIGUOUS' if found else 'NOT FOUND'}; "
                  f"candidates: {found if isinstance(found, list) else ''}")
            continue
        old_title = found
        tier = puzzles[idx].get("difficulty", "medium")
        old_theme = theme_of(cls, old_title)

        if forced_title:
            strict, _, status = build_strict(forced_title.strip(), tier)
            if status != "ok" or is_excluded(strict["categories"]):
                print(f"!! forced '{forced_title}' build status={status} / excluded -> skip")
                continue
            new_theme, new_title = theme_of(cls, forced_title.strip()), forced_title.strip()
        else:
            # try spares in order; skip any that fail the build or are excluded
            # (blogger/leak/military) by marking them used and re-picking
            new_theme = new_title = strict = None
            for _try in range(12):
                pick = pick_spare(spares, used, tier, old_theme, day_theme_counts,
                                  forced_theme=forced_theme.strip() if forced_theme else None)
                if not pick:
                    break
                cand_theme, cand_title = pick
                cand_strict, _, status = build_strict(cand_title, tier)
                if status == "ok" and not is_excluded(cand_strict["categories"]):
                    new_theme, new_title, strict = cand_theme, cand_title, cand_strict
                    break
                print(f"   .. spare '{cand_title}' {status}/excluded -> next")
                used.add(norm(cand_title))  # don't offer this one again
            if not new_title:
                print(f"!! no usable {tier} spare for '{old_title}' "
                      f"(theme {old_theme}); expand the pool")
                continue

        used.add(norm(new_title))
        day_theme_counts[old_theme] -= 1
        day_theme_counts[new_theme] += 1
        plan.append((idx, old_title, old_theme, new_title, new_theme, tier, strict))

    if not plan:
        print("nothing to do.")
        return

    print(f"\n=== day{n} replacements ({'DRY' if dry else 'APPLY'}) ===")
    for idx, ot, oth, nt, nth, tier, strict in plan:
        print(f"  [{idx}] {tier:<6} {ot} ({oth})  ->  {nt} ({nth})")
        print(f"        cats: {' | '.join(strict['categories'][:6])}"
              + (" ..." if len(strict["categories"]) > 6 else ""))

    # balance check
    for idx, *_rest, strict in [(p[0], p[-1]) for p in plan]:
        puzzles[idx] = strict
    tcount = Counter(p.get("difficulty", "medium") for p in puzzles)
    thcount = Counter(theme_of(cls, rt(p["reveal"])) for p in puzzles)
    over = [f"{th}={c}" for th, c in thcount.items()
            if c > (SPORT_CAP if th == "sport" else THEME_CAP)]
    print(f"\n  tiers={dict(tcount)} themes={len(thcount)} "
          f"{'OK' if len(thcount) >= MIN_THEMES and not over else 'WARN ' + str(over)}")

    if dry:
        print("\n(dry run -- not written; drop --dry to apply)")
        return
    json.dump(d, open(day_path(n), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    add_banned([p[1] for p in plan])  # ban removed titles -> never re-offered
    print(f"\nwrote {day_path(n)} (banned {len(plan)} removed titles). "
          f"Now: python3 spares.py && python3 check_days.py "
          f"&& (cd ../app && npm run build)")


if __name__ == "__main__":
    main()
