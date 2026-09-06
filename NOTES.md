# Notes

## 2026-07-03 — Realia pipeline (fewer people, more "вещи")

Goal (Amal): the pool had **too many people**; add non-person realia — sports,
phenomena, objects, works (bands/novels/paintings instead of artists), concepts.

Measured days 30–64: **46% people** (sport 91%, lit 77%, music 71%, art 70%;
games/geography healthy). Root cause: seed = most-viewed articles ⇒ celebrities.

What we built (see `scripts/REALIA_PIPELINE.md` for details):
- `scripts/fetch_realia.py` — BFS ~45 ru.wiki realia categories → **19 193** titles
  → pageviews prefilter → **1 361** famous realia (pv≥3000).
- categories cache `_cats_cache.json` in `build_pool.fetch_categories` (was
  re-fetching the same rate-limited API 3×).
- `classify_pool.py` now folds in `_realia_titles.json`.
- `retier_realia.py` — re-tier realia among themselves → **275/275/274**
  easy/medium/hard (were 80% "hard" under global celebrity-dominated terciles).
- `prep_screen_realia.py` + `verify_screen_realia.py` — solvability screen for the
  new realia only, **merging** into `_solvable.json` (never drops screened people).
- screened **757** realia via a 38-agent swarm.

Design decisions: keep `PV_FLOOR=5000` for people (lowering globally re-admits
obscure celebrities), use a lower **realia floor 3000**; planned `compose_days`
**person cap ≤5/day** so the skew can't return.

Held for this pool: pending day 30–45 replacements (13 approved + 4 re-picks from
a playtest) — apply from the realia-rich pool once the screen + spares finish.

## Inspirations

### Krazydad (krazydad.com)
Jim Bumgardner's free printable + interactive puzzle site. Huge, well-organized catalog of
puzzle types — good reference for breadth of mechanics and for difficulty/volume structuring.
Scouted 2026-06-08.

**Scale:** ~46 main puzzle types (each own directory) + ~46 variants/sub-collections.

**Types worth stealing ideas from:**
- Number/logic: Sudoku (+ Killer, Jigsaw, X, Hex, Samurai, Frame, Sandwich, Kropki,
  Consecutive, Skyscraper, Comparison families), Kakuro, Futoshiki, Inkies (KenKen-style),
  Suguru, Kidoku.
- Spatial/path: Slitherlink, Masyu, Bridges (Hashi), Galaxies (Tentai Show), Train Tracks,
  Vermicelli, Mazes, Akari (Light-up), Star Battle, 7 Queens, Corral, Ripple Effect.
- Binary/grid: Binox (Binairo), Battleships, Limesweeper (minesweeper-ish), Haunted.
- Other: Cross Figures, TripleCross, Circle 9, Troix, Krypto Kakuro, Dumplings, Split Ends.

**Why interesting for us:** each type ships in graded difficulty tiers and "volumes" of
booklets — a clean model for daily/escalating-round content. Many are language-agnostic
(pure logic), unlike our category/text guessing game.

**Download structure (verified):** PDFs live on CDN `files.krazydad.com`, NOT on
`krazydad.com` (latter returns 403 hotlink-protection). Two patterns:
1. Direct files: `files.krazydad.com/{type}/Name.pdf` (e.g. mazes, kakuro).
2. Volume booklets: `files.krazydad.com/{type}/sfiles/{code}_bNNN.pdf` (e.g. sudoku,
   slitherlink); booklet links generated on `krazydad.com/{type}/index.php?vol=N&fmt=...`.

**Full catalog saved:**
- `~/Desktop/krazydad/krazydad_catalog.md` — readable table (all types, paths, descriptions)
- `~/Desktop/krazydad/data/krazydad_catalog.json` — machine-readable (for a downloader script)

**Licensing — IMPORTANT:** Krazydad puzzles require the creator's permission for app/website
use. Jim Bumgardner has granted us **up to 20 puzzles per category**. Full terms, required
attribution, and compliance checklist are in `CREDITS.md`. Must show attribution in-app and
keep the permission email on file.

**Sampler PDFs downloaded** (mechanics reference / source material):
- `~/Desktop/train_tracks/sources/` — 17 PDFs (1 per difficulty×volume) + `train_tracks.zip`
- `~/Desktop/battleships/sources/` — 30 PDFs (1 per size×volume) + `battleships.zip`

TODO (later): decide which logic-puzzle mechanics (if any) fold into the game; if we ship any
Krazydad puzzles, stay within the 20-per-category grant and wire up the attribution.
