#!/usr/bin/env python3
"""Convert a curated day (prototype/data/dayN.json) into the STRICT privacy
format shipped to the SvelteKit client.

Strict format ships, per puzzle:
  - categories : the clue (public, from Wikipedia/GFDL)
  - accept     : sha256(norm(form)) for the title + each accepted alias
                 -> guesses are checked by hashing input; no plaintext answers
  - reveal     : base64(utf-8 title) -> obfuscated; decoded ONLY after solve/giveup
                 (this is obfuscation, not encryption: a determined user can
                  decode it. That is the honest ceiling for a static site.)

The plaintext title and the giveaway wiki URL are NOT shipped; the client
reconstructs the wiki link from the decoded title at reveal time.

Usage: fbpython make_day.py 1   # reads prototype/data/day1.json
"""
import base64
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def norm(s):
    s = s.lower().replace("ё", "е")
    s = re.sub(r"\([^)]*\)", " ", s)        # drop "(фильм)", "(Мюнхен)"
    s = re.sub(r"[^а-яa-z0-9 ]", " ", s)    # punctuation -> space
    return re.sub(r"\s+", " ", s).strip()


# A puzzle answer is a PERSON if any of its Wikipedia categories is a
# birth/death category ("Родившиеся в ...", "Умершие в ..."). Films, books,
# paintings, places, animals, spacecraft never carry these -> reliable signal.
PERSON_RE = re.compile(r"Родивш|Умерш")


def derive_surname(title, categories):
    """Return the surname (last name) to also accept, or None.

    Only persons get surname acceptance. Rules:
      - "Фамилия, Имя [Отчество]" (ru.wiki comma form) -> part before the comma.
      - "Имя [...] Фамилия" (natural order)            -> last whitespace token.
    The first name alone is NEVER returned, so "Македонский" counts for
    "Александр Македонский" while "Александр" does not.
    """
    if not any(PERSON_RE.search(c) for c in categories):
        return None
    t = re.sub(r"\([^)]*\)", " ", title).strip()   # drop disambiguators
    if "," in t:
        surname = t.split(",", 1)[0].strip()
    else:
        parts = t.split()
        if len(parts) < 2:
            return None                            # mononym == full title already
        surname = parts[-1].strip()
    return surname or None


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def b64(s):
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def main():
    day_n = sys.argv[1] if len(sys.argv) > 1 else "1"
    src_path = os.path.join(ROOT, "prototype", "data", f"day{day_n}.json")
    src = json.load(open(src_path, encoding="utf-8"))

    puzzles = []
    for p in src["puzzles"]:
        forms = set(p.get("accept", [])) | {norm(p["title"])}
        # surname acceptance: explicit override, else auto-derive for persons
        if "surname" in p:
            if p["surname"]:
                forms.add(norm(p["surname"]))
        else:
            sn = derive_surname(p["title"], p["categories"])
            if sn:
                forms.add(norm(sn))
        puzzles.append({
            "categories": p["categories"],
            "accept": sorted(sha256(f) for f in forms),
            "reveal": b64(p["title"]),
        })

    out = {"day": src["day"], "puzzles": puzzles}
    out_dir = os.path.join(ROOT, "app", "src", "lib", "days")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"day{day_n}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(puzzles)} strict puzzles -> {out_path}")
    # sanity: no plaintext title/wiki leaked
    blob = open(out_path, encoding="utf-8").read()
    leaked = [p["title"] for p in src["puzzles"] if p["title"] in blob]
    print("plaintext titles leaked:", leaked or "none")


if __name__ == "__main__":
    main()
