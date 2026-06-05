# ru-catfishing — global stats backend (Cloudflare Worker + D1)

Personal stats live in the player's browser (localStorage). This tiny serverless
API holds ONLY anonymous cross-player aggregates: per-day score distributions,
per-puzzle "% got it right", and Wikipedia-open counters. No accounts, no PII.

This is the same recipe Matthew's catfishing.net uses: SvelteKit SPA on a static
host + a small backend just for the global numbers.

## One-time deploy (run from your own terminal)

```bash
cd backend
npm i -g wrangler            # or: npx wrangler ...
wrangler login              # interactive — opens browser

# 1. create the D1 database, then paste the printed database_id into wrangler.toml
wrangler d1 create ru-catfishing-stats

# 2. create the tables (local + remote)
wrangler d1 execute ru-catfishing-stats --remote --file=./schema.sql

# 3. deploy the worker
wrangler deploy
```

`wrangler deploy` prints a URL like `https://ru-catfishing-stats.<you>.workers.dev`.

## Wire it to the app

Put that URL in `app/src/lib/config.js`:

```js
export const STATS_API = 'https://ru-catfishing-stats.<you>.workers.dev';
```

Leave it `''` to run the app with **local-only** stats (the client no-ops every
network call, so nothing breaks before the worker exists).

Then rebuild/redeploy the app (push to main → GitHub Actions).

## Endpoints

| Method | Path | Body / query | Purpose |
|---|---|---|---|
| POST | `/result` | `{day, score2, cells[], clientId}` | record a finished day (idempotent per client) |
| POST | `/open` | `{day, idx}` | increment a Wikipedia-open counter |
| GET | `/agg` | `?days=0,1,2,...` | distributions + per-puzzle counts + global avg + top opens |

`score2 = round(points * 2)` (so 7.5 → 15), range 0..20.

## CORS

`wrangler.toml` `[vars] ALLOWED_ORIGINS` lists the allowed origins (the live Pages
URL + localhost dev ports). Add any new origin there and `wrangler deploy` again.

## Notes / limits

- Abuse: write endpoints are unauthenticated (like the original). `clientId`
  dedupes honest double-submits; a determined user can still skew numbers. Fine
  for a hobby game. If it ever matters, add per-IP rate limiting in the worker.
- Free tier (D1 + Workers) is far beyond what this traffic needs.
- Back up: D1 has time-travel/restore; export with `wrangler d1 export`.
