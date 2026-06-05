# ru-catfishing

A small daily web game: **guess the Russian Wikipedia article from its
categories.** 10 puzzles a day, shareable result (Wordle-style), zero login.

Inspired by *catfishing*: original concept by Sumana Harihareswara; name and
original implementation by Kevan Davis (2006); the modern daily game at
catfishing.net is made by an anonymous developer, Matthew. This is an independent
Russian-language build.

🐟 Live: https://imangulova.github.io/ru-catfishing/

## Structure
- `app/` — the production game: **SvelteKit + adapter-static**, deployed to
  GitHub Pages via Actions. Strict privacy: ships only categories + hashed
  accepted answers + base64-obfuscated reveal (no plaintext answers in client).
- `prototype/` — v0 single-file HTML prototype (kept for reference).
- `scripts/` — Python helpers:
  - `build_pool.py` — fetch RU featured/good articles, filter categories, hash.
  - `make_day.py` — turn a curated day into the strict client data format.
- `research/` — notes on games we learn from (`catfishing.md`).
- `BACKLOG.md` — epics and progress.

## Run the app locally
```bash
cd app
npm install
npm run dev      # dev server
npm run build    # static build -> app/build/
```

## Deploy
Push to `main` → GitHub Actions builds `app/` and deploys to Pages
(`.github/workflows/deploy.yml`). Pages Source must be set to **GitHub Actions**.
`BASE_PATH` is derived from the repo name automatically.

## North star
Daily puzzle + tiny shareable result + zero login. Cheap to host
(static site on GitHub Pages).

## Attribution
- Original concept: Sumana Harihareswara.
- Name and original implementation: Kevan Davis (2006).
- The modern daily game (catfishing.net): an anonymous developer, Matthew.
- This project (ru-catfishing) is an independent Russian-language build.
- Data: ru.wikipedia category data, GFDL.
