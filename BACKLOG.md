# Backlog — Russian Catfishing (v1)

Goal: a Russian-language "guess the Wikipedia article from its categories" daily
game. Static site on GitHub Pages, zero login, shareable result. Data from
ru.wikipedia (GFDL), generated offline and committed as JSON.

Status legend: [ ] todo  [~] in progress  [x] done

---

## Epic 0 — Decisions & spec
- [x] Tech stack: **SvelteKit + adapter-static**, deployed to Pages via Actions
- [x] Privacy model: **B — ship categories + hash(answer)**; autocomplete over
      public RU title corpus; no answer list in client
- [x] Puzzle format: **10 puzzles/day**, curated by hand.
- [x] Attempts: **3 tries** per puzzle, no cross-player scoring in v1. Difficulty = hard.
- [ ] Write a short spec.md from the above.

Locked stack implications:
- Data pipeline (Python) emits JSON with `{categories[], answer_hash}` only.
- Hashing: normalize the guess (trim, lowercase, ё→е) before hashing so minor
  input differences still match. Pick one hash (e.g. SHA-256) used both sides.
- GitHub Actions builds SvelteKit and deploys to Pages (no manual build commits).

## Epic 1 — Data pipeline (scripts/, Python)
- [ ] Fetch candidate articles from ru.wikipedia MediaWiki API
      (start from Избранные/Хорошие статьи + high-pageview articles for "interesting")
- [ ] For each article, fetch its categories
- [ ] Filter out service categories (Википедия:, "Категории по…", hidden/maintenance)
- [ ] Filter out "giveaway" categories (containing a word from the article title)
- [ ] Keep only articles with >= 4 useful categories
- [ ] Build autocomplete title corpus (just RU titles — public, not secret)
- [ ] Emit puzzle pool JSON: {categories[], answer_hash, answer (if model A)}
- [ ] Make the script idempotent + cached (don't re-hit API every run)

## Epic 2 — Daily selection
- [ ] Deterministic daily pick from the pool (seed = date), no server needed
- [ ] Same puzzle for everyone on a given day (timezone decision: UTC? MSK?)
- [ ] Guard against repeats until pool exhausted

## Epic 3 — Game UI
- [x] Show today's category list for the hidden article (v0 prototype)
- [ ] Guess input with autocomplete over RU title corpus (still uses alias-hashes for now)
- [x] Reveal-on-correct; track attempts; win/lose states (v0)
- [ ] "Skip / next puzzle" across the day's N puzzles
- [ ] "Flag stupid" button (broad/giveaway puzzle) — store locally for now
- [x] Russian UI copy throughout (v0)

## Epic 4 — Share loop  (design FIRST conceptually, build here)
- [x] Spoiler-free result string (emoji grid) (v0)
- [x] Copy-to-clipboard button (v0)
- [ ] OG share image for link previews
- [ ] Decide what the line encodes (per-puzzle solved/attempts? total score?)

## Epic 5 — Hosting & deploy
- [x] Pages source: **GitHub Actions** (workflow deploy)
- [x] Enable GitHub Pages -> https://imangulova.github.io/ru-catfishing/
- [x] GitHub Actions workflow: build app/ + deploy (.github/workflows/deploy.yml)
- [ ] Custom domain? (optional, later)

## Epic 6 — Polish
- [ ] PWA: manifest + icons + theme color (installable, offline shell)
- [x] Persist day progress locally (localStorage) (v0)
- [x] Dark/light theme (v0)
- [ ] Accessibility pass (keyboard, contrast)

## Epic 7 — Quality of puzzles
- [ ] Tune category filters (the hard part — junk categories ruin the game)
- [ ] Difficulty estimate per puzzle (e.g. by article pageviews / category count)
- [ ] Optional: collect flags to prune bad puzzles

## Epic 8 — OPTIONAL backend (only if we want real scoring/leaderboard)
- [ ] Serverless validator (Cloudflare Workers free tier) holding answer list
- [ ] Per-puzzle success-rate tracking → difficulty-weighted scoring (Kevan-style)
- [ ] Global stats / leaderboard

---

## Notes on "closed article list"
- GitHub Pages serves everything publicly; anything in the browser is inspectable.
- Privacy options: (A) ship answers — discoverable; (B) ship categories +
  hash(answer) — answers not directly present; (C) serverless — truly hidden.
- A private SOURCE repo can feed a public build via Actions (hides curation, not
  the shipped output).

## Attribution
- Original concept: Sumana Harihareswara. Name and original implementation:
  Kevan Davis (2006). The modern daily game at catfishing.net is made by an
  anonymous developer, Matthew. Our build is an independent RU implementation.
- Data: ru.wikipedia category data, GFDL.
