#!/usr/bin/env python3
"""Build a day's STRICT puzzle json from a raw, human-editable txt list.

This is the *only* file you edit by hand:
    prototype/data/dayN.txt   (gitignored — plaintext titles, never shipped)

We read the titles, fetch + filter their ru.wiki categories, then emit the
strict client format (sha256 accept hashes + base64 reveal). The strict json is
generated, never hand-edited; you should not need to open it at all.

txt format (one puzzle per line):
    Название статьи
    Название статьи | алиас1, алиас2          # extra accepted spellings
    # lines starting with '#' are comments / ignored
    day: 1                                     # optional; else taken from CLI/filename

Usage:
    fbpython make_day_from_txt.py 1            # reads prototype/data/day1.txt
"""
import base64
import hashlib
import json
import os
import re
import sys

# Reuse the vetted fetch/filter logic from build_pool and the surname logic
# from make_day, so there is a single source of truth for each rule.
from build_pool import (
    fetch_categories,
    fetch_langlink,
    fetch_redirects,
    is_giveaway,
    is_service,
    title_tokens,
)
from make_day import derive_surname, norm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def b64(s):
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def parse_txt(path):
    """Return (day_value, [{title, accept[]}]) from the raw txt file."""
    day_value = None
    puzzles = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("day:"):
                day_value = line.split(":", 1)[1].strip()
                continue
            title, _, alias_part = line.partition("|")
            title = title.strip()
            aliases = [a.strip() for a in alias_part.split(",") if a.strip()]
            puzzles.append({"title": title, "accept": aliases})
    return day_value, puzzles


def build_puzzle(entry):
    """Fetch categories, filter, and return (strict_puzzle, preview_dict)."""
    title = entry["title"]
    cats = fetch_categories(title)
    # Compute giveaway tokens from the title WITHOUT its "(...)" disambiguator,
    # so "(роман)" / "(фильм)" don't leak generic words like "роман" and wrongly
    # nuke real clue categories ("Романы-антиутопии"). The disambiguator is not
    # part of the actual name, so it must not act as a giveaway.
    tokens = title_tokens(re.sub(r"\([^)]*\)", " ", title))
    useful = sorted(
        c for c in cats if not is_service(c) and not is_giveaway(c, tokens)
    )

    forms = {norm(title)} | {norm(a) for a in entry["accept"]}
    sn = derive_surname(title, useful)
    if sn:
        forms.add(norm(sn))

    # Cross-language acceptance: also accept the English-Wikipedia title (and its
    # surname for persons), so "Conan Doyle" works as well as "Конан Дойль".
    en = fetch_langlink(title, "en")
    if en:
        forms.add(norm(en))
        en_sn = derive_surname(en, useful)
        if en_sn:
            forms.add(norm(en_sn))

    # Redirect aliases: every ru.wiki redirect to the article is an accepted
    # alternative name/spelling (real names, Latin binomials, variants).
    for red in fetch_redirects(title):
        forms.add(norm(red))

    forms.discard("")  # drop empties (emoji/punctuation-only redirects, etc.)
    strict = {
        "categories": useful,
        "accept": sorted(sha256(f) for f in forms),
        "reveal": b64(title),
    }
    preview = {"title": title, "n_cats": len(useful), "categories": useful}
    return strict, preview


def main():
    day_n = sys.argv[1] if len(sys.argv) > 1 else "1"
    src_path = os.path.join(ROOT, "prototype", "data", f"day{day_n}.txt")
    if not os.path.exists(src_path):
        sys.exit(f"missing raw source: {src_path}\n"
                 f"create it (one article title per line) and rerun.")

    day_value, entries = parse_txt(src_path)
    day_value = day_value or day_n

    strict_puzzles = []
    print(f"building day {day_value} from {len(entries)} titles\n")
    for i, entry in enumerate(entries, 1):
        strict, preview = build_puzzle(entry)
        strict_puzzles.append(strict)
        flag = "  <-- LOW (<4)" if preview["n_cats"] < 4 else ""
        print(f"{i:2}. {preview['title']}  ({preview['n_cats']} cats){flag}")
        print("    " + " · ".join(preview["categories"]))

    out = {"day": day_value, "puzzles": strict_puzzles}
    out_dir = os.path.join(ROOT, "app", "src", "lib", "days")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"day{day_n}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # leak check: no plaintext title may appear in the strict json
    blob = open(out_path, encoding="utf-8").read()
    leaked = [e["title"] for e in entries if e["title"] in blob]
    print(f"\nwrote {len(strict_puzzles)} strict puzzles -> {out_path}")
    print("plaintext titles leaked:", leaked or "none")


if __name__ == "__main__":
    main()
