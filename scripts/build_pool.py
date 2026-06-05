#!/usr/bin/env python3
"""Build a Russian-catfishing puzzle pool from ru.wikipedia.

Source = ru.wiki Featured ("Избранные") + Good ("Хорошие") articles: these are
guaranteed to be detailed Russian articles, and tend to be good guessing targets.

For each article we fetch its (non-hidden) categories, drop service / giveaway
ones, and keep articles with >= MIN_CATEGORIES useful categories. Output ships
ONLY {categories[], answer_sha256} so the answer list is not present in clients.

Usage:
    fbpython build_pool.py --limit 12            # small demo
    fbpython build_pool.py --limit 300 --out ../prototype/static/pool.json
"""
import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://ru.wikipedia.org/w/api.php"
UA = "game-designer/0.1 (personal project; imangulovamal@gmail.com)"
MIN_CATEGORIES = 4

# Featured + Good article tracking categories (members are ns0 articles).
SEED_CATEGORIES = [
    "Категория:Википедия:Избранные статьи по алфавиту",
    "Категория:Википедия:Хорошие статьи по алфавиту",
]

# Hidden maintenance categories are already dropped via clshow=!hidden.
# We additionally drop only pure navigation filler. NOTE: birth/death-year
# categories ("Родившиеся в 1892 году") are KEPT — they are real clues that
# help unwind the answer. Only "...по алфавиту" is removed.
SERVICE_PATTERNS = [
    "по алфавиту",   # "Персоналии по алфавиту", "Картины по алфавиту", ...
    "Википедия:",    # any non-hidden project-namespace category
]


def api_get(params, max_retries=6):
    """GET the API with polite retry/backoff on 429 + transient 5xx errors.

    Wikipedia rate-limits anonymous bursts; on 429 it sends a Retry-After header
    we honour, otherwise we exponential-backoff (2,4,8,16,... up to 60s).
    """
    params = {**params, "format": "json", "formatversion": "2"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                wait = int(retry_after) if (retry_after and retry_after.isdigit()) else min(60, 2 ** (attempt + 1))
                print(f"  [{e.code}] backing off {wait}s (attempt {attempt + 1})", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            if attempt < max_retries - 1:
                wait = min(60, 2 ** (attempt + 1))
                print(f"  [URLError {e.reason}] retry in {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise


def fetch_seed_titles(limit):
    """Pull article titles, spread across the alphabet for variety."""
    titles = []
    for cat in SEED_CATEGORIES:
        cont = None
        while len(titles) < limit * 3:
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
    # spread: take every Nth so we don't get only "А..." military hardware
    if len(titles) > limit:
        step = len(titles) // limit
        titles = titles[::step][:limit]
    return titles


def fetch_categories(title):
    """Non-hidden categories of an article, with the 'Категория:' prefix removed."""
    data = api_get({
        "action": "query", "prop": "categories", "titles": title,
        "cllimit": "500", "clshow": "!hidden", "redirects": "1",
    })
    page = data["query"]["pages"][0]
    cats = [c["title"].split(":", 1)[1] for c in page.get("categories", [])]
    return cats


def fetch_langlink(title, lang="en"):
    """The article's title on another-language Wikipedia (via langlinks), or None.

    Used to accept cross-language answers for foreign realities: e.g. the ru
    article "Артур Конан Дойл" has an `en` langlink "Arthur Conan Doyle", so a
    player can answer in English. The returned title goes through the same norm()
    (lowercase, dashes->space, word-order-independent) as everything else.
    """
    data = api_get({
        "action": "query", "prop": "langlinks", "titles": title,
        "lllang": lang, "lllimit": "1", "redirects": "1",
    })
    page = data["query"]["pages"][0]
    lls = page.get("langlinks") or []
    return lls[0]["title"] if lls else None


def fetch_redirects(title):
    """All ns0 redirect titles that point to `title`, as a list of strings.

    Wikipedia redirects are the curated set of alternative names/spellings for an
    article: real names ("Фаррух Булсара" -> "Фредди Меркьюри"), cross-language
    forms ("Freddie Mercury"), Latin binomials ("Phascolarctos cinereus" ->
    "Коала"), and common variants. We add each (after norm()) as an accepted
    answer, so a player who knows any alias still scores. Non-article junk
    (emoji-only redirects, etc.) normalizes to '' and is dropped by the caller.
    """
    out = []
    cont = None
    while True:
        params = {
            "action": "query", "prop": "redirects", "titles": title,
            "rdnamespace": "0", "rdlimit": "max", "redirects": "1",
        }
        if cont:
            params["rdcontinue"] = cont
        data = api_get(params)
        pages = data.get("query", {}).get("pages") or [{}]
        out += [r["title"] for r in pages[0].get("redirects", [])]
        cont = data.get("continue", {}).get("rdcontinue")
        if not cont:
            break
        time.sleep(0.1)
    return out


# Common words that may appear in a title but are NOT giveaways (so birth/death
# YEAR categories survive: "Времена года" must not nuke "Картины 1873 года").
GIVEAWAY_STOPWORDS = {
    "года", "году", "годы", "годов", "веке", "века", "веков",
    "после", "часть", "имени", "около",
}


def norm(s):
    return s.lower().replace("ё", "е")


def title_tokens(title):
    # distinctive title words (len >= 4, minus stopwords) used to detect giveaways
    words = re.findall(r"[а-яёa-z0-9]+", norm(title))
    return {w for w in words if len(w) >= 4 and w not in GIVEAWAY_STOPWORDS}


def is_service(cat):
    return any(p in cat for p in SERVICE_PATTERNS)


def is_giveaway(cat, tokens):
    # substring match catches inflected forms: "выборг" in "выборгского района"
    c = norm(cat)
    return any(tok in c for tok in tokens)


def normalize_answer(title):
    return title.strip().lower().replace("ё", "е")


def answer_hash(title):
    return hashlib.sha256(normalize_answer(title).encode("utf-8")).hexdigest()


def build(limit, sleep=0.4, out=None, checkpoint_every=50):
    titles = fetch_seed_titles(limit)
    pool = []
    for idx, title in enumerate(titles):
        try:
            cats = fetch_categories(title)
        except Exception as e:  # one bad article must not kill a 1000-article run
            print(f"  skip {title!r}: {e}", file=sys.stderr)
            time.sleep(sleep)
            continue
        tokens = title_tokens(title)
        useful = [c for c in cats if not is_service(c) and not is_giveaway(c, tokens)]
        if len(useful) >= MIN_CATEGORIES:
            pool.append({
                "title": title,            # kept here for OUR curation only
                "categories": sorted(useful),
                "answer_sha256": answer_hash(title),
                "n_raw_categories": len(cats),
            })
        if out and (idx + 1) % checkpoint_every == 0:
            with open(out, "w", encoding="utf-8") as f:
                json.dump(pool, f, ensure_ascii=False, indent=2)
            print(f"  …checkpoint {idx + 1}/{len(titles)} titles, {len(pool)} kept", file=sys.stderr)
        time.sleep(sleep)
    return pool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--out", default=None)
    ap.add_argument("--sleep", type=float, default=0.4, help="seconds between article fetches")
    args = ap.parse_args()

    pool = build(args.limit, sleep=args.sleep, out=args.out)
    if args.out:
        # client build should strip "title"; kept in dev output for review
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(pool, f, ensure_ascii=False, indent=2)
        print(f"wrote {len(pool)} puzzles -> {args.out}", file=sys.stderr)
    else:
        for p in pool:
            print(f"\n### {p['title']}  (sha {p['answer_sha256'][:10]}…)")
            print("    " + " · ".join(p["categories"]))
        print(f"\n[{len(pool)} playable puzzles]", file=sys.stderr)


if __name__ == "__main__":
    main()
