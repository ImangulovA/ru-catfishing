# Realia sourcing pipeline

Tooling to widen the puzzle pool with **non-person "realia"** — things, works, and
concepts — instead of yet more people. Added 2026-07-03.

## Why

The candidate pool is seeded from most-viewed articles (`fetch_top.py`), which
skews heavily to celebrities. Measured over days 30–64: **46% of puzzles are
people**, worst in `sport` 91%, `literature` 77%, `music` 71%, `art` 70% — because
the seed pulls *artists* rather than their *works*. `games` (0%) and `geography`
(9%) are healthy. This pipeline seeds bands/albums, novels/plays, paintings, sports
as types, mythical creatures, natural phenomena, food, breeds, elements, space,
objects, and cognitive/philosophical concepts.

## Data files (author-only, gitignored)

- `_realia_raw.json` — `{seed category: [gathered titles]}` (checkpointed, resumable).
- `_realia_titles.json` — famous realia kept after the pageviews prefilter.
- `_cats_cache.json` — persistent article→categories cache (see below).
- `_pageviews_cache.json` — shared pageviews cache (warmed by the prefilter).

## Scripts

### `fetch_realia.py`
Walks a curated set of ru.wiki categories (BFS over subcategories, depth 2 — the
real lists live in `…по алфавиту` subcats) and collects article titles, then keeps
only the famous ones.

- `python3 fetch_realia.py --gather` — BFS categories → `_realia_raw.json`. Merges
  into existing raw and **checkpoints per seed** (resumable). Cheap-ish.
- `python3 fetch_realia.py` — reuse raw (or gather) → pageviews prefilter →
  `_realia_titles.json`.

**Rate-limit lessons (important):**
- `ru.wikipedia.org/w/api.php` rate-limits hard (HTTP 429). Use ≥0.3 s between
  requests + exponential backoff (built in).
- The pageviews prefilter uses a **direct REST call** (`pv_rest`,
  `wikimedia.org/.../pageviews`, no ru.wiki redirect resolve). `fetch_pageviews`
  in `classify.py` resolves redirects via `api.php` internally and 429s to death;
  `pv_rest` avoids that and is ~0.18 s/title.

### categories cache (`build_pool.py`)
`fetch_categories` now caches to `_cats_cache.json`. Before, `classify_pool.py` and
the screen prep each re-fetched the same categories from the rate-limited API.
`classify_pool.py` flushes the cache at the end, so later steps hit the cache.

### `classify_pool.py`
Folds `_realia_titles.json` into the theme/difficulty map alongside `_top_titles.json`,
writing `_classified.json = {title: {theme, pv, n_cats, tier}}`.

### `retier_realia.py`
Global tiers are terciles over a pool dominated by high-pageview celebrities, so
realia (lower pv) almost all land in `hard`. This re-tiers realia among
**themselves** (terciles over realia only) so they populate `easy`/`medium`/`hard`
evenly. People keep their global tiers. `--dry` previews.

### `prep_screen_realia.py` / `verify_screen_realia.py`
Solvability screen for **new realia only** (people are already in `_solvable.json`).
`prep_screen_realia.py` writes `/tmp/screen_realia/{map.json, batch_NNN.txt}`
(id + categories, no titles). A swarm of agents blind-guesses each batch; the
collected `{id: guess}` go to `/tmp/screen_realia/guesses.json`.
`verify_screen_realia.py` checks the guesses (norm + expand_forms + surname) and
**merges** the solvable titles into `_solvable.json` (union — it never overwrites
the already-screened people, unlike the original `verify_screen.py`).

## Run order

```
python3 fetch_realia.py --gather          # ru.wiki categories -> _realia_raw.json
python3 fetch_realia.py                    # pv prefilter -> _realia_titles.json
python3 classify_pool.py                   # -> _classified.json (+ warms cats cache)
python3 retier_realia.py                   # realia terciles over themselves
python3 prep_screen_realia.py              # -> /tmp/screen_realia batches
#   ... run the solvability swarm -> /tmp/screen_realia/guesses.json ...
python3 verify_screen_realia.py            # merge solvable realia into _solvable.json
python3 spares.py                          # rebuild spare buckets (now realia-rich)
```

Then `quick_replace.py N "Title"` pulls realia spares like any other, and days can
be de-peopled without breaking the difficulty curve.

## Numbers (2026-07-03)

- Gathered **19 193** unique realia titles across ~45 seed categories.
- Famous realia at pv≥3000: **1 361**; playable (pv≥3000 & ≥4 cats): **824**.
- After re-tier: **275 easy / 275 medium / 274 hard**.
- Screened **757** new realia for solvability (swarm); solvable ones merged into
  `_solvable.json`.
