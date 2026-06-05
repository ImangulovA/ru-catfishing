// ru-catfishing global-stats API (Cloudflare Worker + D1).
//
// Endpoints (all JSON, CORS-guarded):
//   POST /result  {day, score2, cells:["win"|"half"|"miss",...], clientId}
//                 -> records a finished day ONCE per client (idempotent).
//   POST /open    {day, idx}
//                 -> increments the Wikipedia-open counter for that answer.
//   GET  /agg?days=0,1,2,...
//                 -> aggregates: per-day score distribution + per-puzzle outcome
//                    counts (for the requested days), plus global all-time avg,
//                    per-day averages, top-opened articles, total opens.
//
// Personal stats stay in the browser; this only holds anonymous cross-player
// aggregates. clientId is a random UUID from localStorage, used solely to avoid
// double-counting a day.

const MAX_DAYS = 80; // cap /agg fan-out

function corsHeaders(request, env) {
  const origin = request.headers.get('Origin') || '';
  const allowed = (env.ALLOWED_ORIGINS || '').split(',').map((s) => s.trim()).filter(Boolean);
  const ok = allowed.includes(origin);
  return {
    'Access-Control-Allow-Origin': ok ? origin : (allowed[0] || '*'),
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    Vary: 'Origin',
  };
}

function json(data, request, env, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders(request, env) },
  });
}

const isInt = (v, lo, hi) => Number.isInteger(v) && v >= lo && v <= hi;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(request, env) });
    }

    try {
      if (request.method === 'POST' && url.pathname === '/result') {
        return await handleResult(request, env);
      }
      if (request.method === 'POST' && url.pathname === '/open') {
        return await handleOpen(request, env);
      }
      if (request.method === 'GET' && url.pathname === '/agg') {
        return await handleAgg(request, env, url);
      }
      if (request.method === 'GET' && url.pathname === '/') {
        return json({ ok: true, service: 'ru-catfishing-stats' }, request, env);
      }
    } catch (e) {
      return json({ ok: false, error: String(e) }, request, env, 500);
    }
    return json({ ok: false, error: 'not found' }, request, env, 404);
  },
};

async function handleResult(request, env) {
  const body = await request.json().catch(() => null);
  if (!body) return json({ ok: false, error: 'bad json' }, request, env, 400);

  const { day, score2, cells, clientId } = body;
  if (!isInt(day, -10, 100000)) return json({ ok: false, error: 'bad day' }, request, env, 400);
  if (!isInt(score2, 0, 40)) return json({ ok: false, error: 'bad score2' }, request, env, 400);
  if (typeof clientId !== 'string' || clientId.length < 8 || clientId.length > 64) {
    return json({ ok: false, error: 'bad clientId' }, request, env, 400);
  }
  if (!Array.isArray(cells) || cells.length > 15) {
    return json({ ok: false, error: 'bad cells' }, request, env, 400);
  }

  // Idempotency: a client can submit each day only once.
  const claim = await env.DB
    .prepare('INSERT OR IGNORE INTO submissions(client_id, day) VALUES(?, ?)')
    .bind(clientId, day)
    .run();
  if (!claim.meta || claim.meta.changes === 0) {
    return json({ ok: true, duplicate: true }, request, env);
  }

  const stmts = [];
  stmts.push(
    env.DB.prepare(
      'INSERT INTO day_scores(day, score2, cnt) VALUES(?, ?, 1) ' +
        'ON CONFLICT(day, score2) DO UPDATE SET cnt = cnt + 1'
    ).bind(day, score2)
  );
  cells.forEach((c, idx) => {
    const col = c === 'win' ? 'win' : c === 'half' ? 'half' : 'miss';
    stmts.push(
      env.DB.prepare(
        `INSERT INTO puzzle_results(day, idx, win, half, miss) VALUES(?, ?, ` +
          `${col === 'win' ? 1 : 0}, ${col === 'half' ? 1 : 0}, ${col === 'miss' ? 1 : 0}) ` +
          `ON CONFLICT(day, idx) DO UPDATE SET ${col} = ${col} + 1`
      ).bind(day, idx)
    );
  });
  await env.DB.batch(stmts);
  return json({ ok: true }, request, env);
}

async function handleOpen(request, env) {
  const body = await request.json().catch(() => null);
  if (!body) return json({ ok: false, error: 'bad json' }, request, env, 400);
  const { day, idx } = body;
  if (!isInt(day, -10, 100000) || !isInt(idx, 0, 50)) {
    return json({ ok: false, error: 'bad day/idx' }, request, env, 400);
  }
  await env.DB.batch([
    env.DB
      .prepare(
        'INSERT INTO article_opens(day, idx, opens) VALUES(?, ?, 1) ' +
          'ON CONFLICT(day, idx) DO UPDATE SET opens = opens + 1'
      )
      .bind(day, idx),
    env.DB
      .prepare(
        "INSERT INTO counters(name, val) VALUES('total_opens', 1) " +
          'ON CONFLICT(name) DO UPDATE SET val = val + 1'
      ),
  ]);
  return json({ ok: true }, request, env);
}

async function handleAgg(request, env, url) {
  const raw = (url.searchParams.get('days') || '').split(',').map((s) => parseInt(s, 10));
  const days = [...new Set(raw.filter((n) => Number.isInteger(n) && n >= -10))].slice(0, MAX_DAYS);
  const placeholders = days.map(() => '?').join(',');

  // per-day score distribution (for the user's played days) -> avg + percentile
  const dist = {};
  const puzzle = {};
  if (days.length) {
    const ds = await env.DB
      .prepare(`SELECT day, score2, cnt FROM day_scores WHERE day IN (${placeholders})`)
      .bind(...days)
      .all();
    for (const r of ds.results || []) {
      (dist[r.day] ||= {})[r.score2] = r.cnt;
    }
    const pr = await env.DB
      .prepare(`SELECT day, idx, win, half, miss FROM puzzle_results WHERE day IN (${placeholders})`)
      .bind(...days)
      .all();
    for (const r of pr.results || []) {
      (puzzle[r.day] ||= {})[r.idx] = { win: r.win, half: r.half, miss: r.miss };
    }
  }

  // global: per-day averages (all days), all-time avg, top opened, total opens
  const avgRows = await env.DB
    .prepare('SELECT day, SUM(score2 * cnt) AS s, SUM(cnt) AS c FROM day_scores GROUP BY day')
    .all();
  const avgByDay = {};
  let gs = 0;
  let gc = 0;
  for (const r of avgRows.results || []) {
    if (r.c > 0) avgByDay[r.day] = { avg: r.s / (2 * r.c), n: r.c };
    gs += r.s;
    gc += r.c;
  }

  const topRows = await env.DB
    .prepare('SELECT day, idx, opens FROM article_opens ORDER BY opens DESC LIMIT 15')
    .all();
  const totalRow = await env.DB
    .prepare("SELECT val FROM counters WHERE name = 'total_opens'")
    .first();

  return json(
    {
      ok: true,
      dist,
      puzzle,
      avgByDay,
      allTimeAvg: gc > 0 ? gs / (2 * gc) : null,
      totalPlays: gc,
      topOpens: topRows.results || [],
      totalOpens: totalRow ? totalRow.val : 0,
    },
    request,
    env
  );
}
