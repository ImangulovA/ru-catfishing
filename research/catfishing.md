# Catfishing — research notes

Date: 2026-06-05
Status: CONFIRMED from page source (fetched via curl). High confidence.

## TL;DR
"Catfishing" is a guessing game: **given the full list of Wikipedia categories an
article belongs to, guess the article.** There are TWO distinct implementations,
and it's important not to conflate them:

1. **The original idea** — a party game invented by **Sumana Harihareswara (2006)**:
   read a Wikipedia page's category list aloud, others guess the article.
2. **kevan.org/catfishing.php** — **Kevan Davis** automated it (~2006), added a
   scoring system (Apr 2007). PHP. Adding new articles broke in 2009 (Wikipedia
   API change) and was never fixed. This is the "classic" version.
3. **catfishing.net** — a **modern, separate reboot**. Daily format,
   "10 interesting people, places, and things to guess every day." Different
   tech stack entirely (see below). Author not stated on the site (Mastodon
   @catfishing); do NOT assume it's Kevan.

## Confirmed mechanic
- You are shown **all the (useful) Wikipedia categories** of a hidden article.
- You **guess the article**.
- Category cleanup rules (from Kevan's how-to): discard in-house Wikipedia admin
  categories, and discard "giveaway" categories (ones containing a word from the
  article's own title). Article needs >=4 useful categories to be playable.
- "Stupid" flag: mark puzzles where categories are too broad / a giveaway slipped
  through / multiple valid answers. Good crowd-sourced quality control idea.

## Scoring (classic kevan.org version, Apr 2007)
- **Difficulty-weighted**: points = based on how many other players got it.
  - If only 25% got it right -> +75 for correct, -25 for wrong.
  - If 99% got it right -> +1 for correct, -99 for wrong.
- Elegant: rewards obscure knowledge, punishes missing the "easy" ones. Requires
  tracking aggregate per-puzzle success rates across players (needs a backend).

## catfishing.net tech stack  [CONFIRMED from HTML]
- **SvelteKit** SPA. Build artifacts under `/_app/immutable/...` (Svelte's
  signature). `<noscript>JavaScript must be enabled to play this game.</noscript>`
  -> gameplay is fully client-rendered.
- **Sentry** for error monitoring (sentry-trace / baggage meta tags; release tag
  `2026-06-04-1822-...-deploy` -> actively deployed, CI/CD).
- **PWA**: site.webmanifest, apple-touch-icons, theme-color (#022c22 dark green),
  installable.
- Custom fonts: **Alegreya** + Alegreya Sans (self-hosted woff2, preloaded).
- **Social sharing via Open Graph images**: static `sharing-image-1200x630.png`
  etc. (link preview card). Per-result share string is generated client-side
  (could not capture without executing JS — LOW priority to confirm).
- Data: **Wikipedia** category data, GFDL-licensed (rereleased under GFDL).

classic kevan.org version tech: **PHP**, server-rendered, plus a small
`js/wikipedia.js`. Old-school.

## Open source?  [CONFIRMED: NO public repo]
- No github/gitlab/"source code" references anywhere in catfishing.net HTML.
- No /about, no /humans.txt (both 404).
- kevan.org version: closed, like Kevan's other games (Urban Dead etc.).
- Conclusion: **no source available for either.** We learn from the design only.
  (All gameplay *data* is Wikipedia/GFDL, so the data approach is reusable.)

## Still-to-confirm (low priority)
1. Exact per-result share-string format on catfishing.net (needs JS execution).
2. Whether catfishing.net keeps the difficulty-weighted scoring or simplified it.

## Takeaways for OUR game
- **Concept is public-domain-ish**: category->guess is a known party game; data is
  Wikipedia/GFDL. We can build our own variant freely (with attribution).
- catfishing.net proves the modern recipe: **SvelteKit SPA + daily puzzle + PWA +
  OG share image + zero login**. Hostable as a static build (GitHub Pages works).
- Two backend choices:
  - **Static / no backend** (daily seed baked at build time): cheapest, free on
    Pages. Loses cross-player difficulty scoring + global stats.
  - **Tiny backend** (counts per puzzle): unlocks Kevan's difficulty-weighted
    scoring and a global leaderboard. Costs hosting.
- Design the **share string first** — it's the viral loop.
- "Stupid/flag" mechanic is a cheap, smart way to crowd-source puzzle quality.
