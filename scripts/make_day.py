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

from build_pool import fetch_langlink, fetch_redirects

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Function/stop words dropped from answers, symmetric on both sides, so
# "the last of us" == "last of us" and "О дивный новый мир" == "дивный новый мир".
# Keep this in sync with STOPWORDS in app/src/routes/+page.svelte:norm().
STOPWORDS = {"the", "of", "о", "об", "обо", "и", "а", "но", "в", "во", "на", "не"}


def norm(s):
    # Typo-tolerant ("УСЛОВНО зачёт"): fold ё/э->е and й->и, collapse runs of the
    # same char, then SORT the words, so "Хэди Ламарр" / "ламар" all match
    # "Хеди Ламарр" AND "Бергкамп Деннис" matches "Деннис Бергкамп" (word order
    # ignored). MUST stay byte-identical to norm() in app/src/routes/
    # +page.svelte, or guesses won't hash to the shipped accept hashes.
    s = s.lower().replace("ё", "е").replace("э", "е").replace("й", "и")
    s = re.sub(r"\([^)]*\)", " ", s)        # drop "(фильм)", "(Мюнхен)"
    s = re.sub(r"['’‘ʼ`]", "", s)           # апострофы/кавычки -> ничего (д'арк -> дарк)
    s = re.sub(r"[^а-яa-z0-9 ]", " ", s)    # прочая пунктуация -> пробел
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"(.)\1+", r"\1", s)         # удвоенные буквы -> одна (ламарр->ламар)

    # Singular/plural & case tolerance: drop a trailing Russian inflection vowel
    # (or soft sign) so the nominative singular and plural collapse to one stem:
    # "коала"=="коалы", "челюсть"=="челюсти", "окно"=="окна", "кот"=="коты".
    # Only when the remaining stem stays >=3 chars (word length >=4), so short
    # words ("Ра", "Рим") are left intact. MUST stay byte-identical to the
    # same step in app/src/routes/+page.svelte:norm().
    def stem(w):
        return w[:-1] if len(w) >= 4 and w[-1] in "аеиоуыюяь" else w

    # drop English stopwords so "last of us" == "the last of us"
    words = [stem(w) for w in s.split() if w not in STOPWORDS]
    return " ".join(sorted(words))          # порядок слов не важен (Бергкамп Деннис == Деннис Бергкамп)


# Trailing qualifier patterns stripped so the "core" title is also accepted, e.g.
# "Извержение Везувия в 79 году" -> also accept "Извержение Везувия". Each form
# is later norm()+sha256'd into accept, and expand_forms() is applied to the title
# AND to every redirect/langlink so aliases get the same leniency.
TAIL_PATTERNS = [
    r"\s+в\s+\d{1,4}\s+году?$",   # "...в 79 году"
    r"\s+\d{3,4}\s+года$",        # "...1773 года"
    r",?\s+\d{3,4}$",             # хвостовой год ("..., 1979")
    r"\s+[IVXLCDM]{1,7}$",        # хвостовая римская цифра (Клеопатра VII, Елизавета I)
]


def expand_forms(raw):
    """Return {raw} plus 'short' variants with a trailing date/qualifier removed."""
    forms = {raw}
    for pat in TAIL_PATTERNS:
        short = re.sub(pat, "", raw).strip()
        if short and short != raw:
            forms.add(short)
    return forms


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


def given_surname_form(title, categories):
    """For comma-form persons "Фамилия, Имя [Отчество]" return "Имя Фамилия"
    (drops the patronymic) so a player can answer name+surname without it
    ("Матвей Сафонов" for "Сафонов, Матвей Евгеньевич"). None otherwise."""
    if not any(PERSON_RE.search(c) for c in categories):
        return None
    t = re.sub(r"\([^)]*\)", " ", title).strip()
    if "," not in t:
        return None
    surname, rest = t.split(",", 1)
    given = rest.strip().split()
    if not given or not surname.strip():
        return None
    return f"{given[0]} {surname.strip()}"


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
        # Collect every RAW accepted name (title, curated aliases, en title,
        # redirects), each expanded to its short form, THEN norm() them all.
        raws = set(expand_forms(p["title"]))
        for alias in p.get("accept", []):
            raws |= expand_forms(alias)
        # Cross-language acceptance: add the English-Wikipedia title so foreign
        # realities can be answered in English too.
        en = fetch_langlink(p["title"], "en")
        if en:
            raws |= expand_forms(en)
        # Redirect aliases: every ru.wiki redirect to the article is an accepted
        # alternative name/spelling (real names, Latin binomials, variants).
        for red in fetch_redirects(p["title"]):
            raws |= expand_forms(red)
        forms = {norm(r) for r in raws}

        # surname acceptance: explicit override, else auto-derive for persons
        if "surname" in p:
            if p["surname"]:
                forms.add(norm(p["surname"]))
        else:
            sn = derive_surname(p["title"], p["categories"])
            if sn:
                forms.add(norm(sn))
        if en:
            en_sn = derive_surname(en, p["categories"])
            if en_sn:
                forms.add(norm(en_sn))
        gsf = given_surname_form(p["title"], p["categories"])
        if gsf:
            forms.add(norm(gsf))
        forms.discard("")  # drop empties (emoji/punctuation-only redirects)
        puzzles.append({
            "categories": p["categories"],
            "accept": sorted(sha256(f) for f in forms),
            "reveal": b64(p["title"]),
            "difficulty": p.get("difficulty", "medium"),
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
