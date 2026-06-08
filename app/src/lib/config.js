// URL of the global-stats Worker (see backend/README.md). Leave '' to run the
// app with LOCAL-ONLY stats — every network call no-ops, nothing breaks.
// After `wrangler deploy`, paste the printed workers.dev URL here and redeploy.
export const STATS_API = 'https://ru-catfishing-stats.ru-catfishing.workers.dev';

// Password that unlocks playing FUTURE (not-yet-released) days early. Share a
// link like `?unlock=<this>` and the visitor can play ahead; the flag persists
// in localStorage. NOTE: this is an OBFUSCATION gate, not real security — future
// days' data already ships in the static bundle, so anyone reading the source
// can still see them. Change this to whatever you like (it lives in the public
// bundle by design).
export const UNLOCK_PASSWORD = 'rybalka';
