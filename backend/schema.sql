-- ru-catfishing global stats (Cloudflare D1 / SQLite).
-- Personal stats live in the browser (localStorage); ONLY cross-player
-- aggregates live here. No accounts, no PII — just anonymous counters keyed by
-- a client-generated UUID used solely to avoid double-counting a day.

-- Score histogram per day. score2 = round(points * 2), range 0..20 (so 7.5 -> 15).
-- Average for a day = sum(score2 * cnt) / (2 * sum(cnt)); percentile is computed
-- from the cumulative distribution.
CREATE TABLE IF NOT EXISTS day_scores (
  day    INTEGER NOT NULL,
  score2 INTEGER NOT NULL,
  cnt    INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, score2)
);

-- Per-puzzle outcome counts -> "% of players who got it right".
CREATE TABLE IF NOT EXISTS puzzle_results (
  day  INTEGER NOT NULL,
  idx  INTEGER NOT NULL,
  win  INTEGER NOT NULL DEFAULT 0,
  half INTEGER NOT NULL DEFAULT 0,
  miss INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, idx)
);

-- How often players opened each answer's Wikipedia article.
CREATE TABLE IF NOT EXISTS article_opens (
  day   INTEGER NOT NULL,
  idx   INTEGER NOT NULL,
  opens INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, idx)
);

-- One row per (client, day): lets /result be idempotent (a client can submit a
-- given day only once; re-submits are ignored).
CREATE TABLE IF NOT EXISTS submissions (
  client_id TEXT    NOT NULL,
  day       INTEGER NOT NULL,
  PRIMARY KEY (client_id, day)
);

-- Global named counters (e.g. total Wikipedia opens).
CREATE TABLE IF NOT EXISTS counters (
  name TEXT PRIMARY KEY,
  val  INTEGER NOT NULL DEFAULT 0
);
