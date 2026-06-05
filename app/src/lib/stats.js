// Player stats across all days, read from localStorage (rucatfish_day<N>).
// Personal-only (no network). Used on the end screen, the archive calendar, and
// the full /stats page. Global cross-player numbers come from the Worker (api.js).
import { DAYS, currentDay } from './days/index.js';

export function computeStats(now = new Date()) {
  if (typeof localStorage === 'undefined') return null; // SSR / prerender

  const entries = {};
  for (const idx of Object.keys(DAYS).map(Number)) {
    const d = DAYS[idx];
    let saved = null;
    try {
      saved = JSON.parse(localStorage.getItem('rucatfish_day' + d.day));
    } catch (e) {}
    if (!saved || !Array.isArray(saved.results)) continue;
    const results = saved.results;
    const answered = results.filter((r) => r !== null).length;
    const wins = results.filter((r) => r === 'win').length;
    const halves = results.filter((r) => r === 'half').length;
    const losses = results.filter((r) => r === 'lose').length;
    entries[idx] = {
      idx,
      finished: !!saved.done || answered === results.length,
      live: saved.live === true, // played on the puzzle's own date
      points: wins + halves * 0.5,
      n: results.length,
      wins,
      halves,
      losses,
      cells: results.map((r) => (r === 'win' ? 'win' : r === 'half' ? 'half' : 'miss')),
    };
  }

  const finishedIdx = Object.values(entries)
    .filter((e) => e.finished)
    .map((e) => e.idx)
    .sort((a, b) => a - b);
  const finishedSet = new Set(finishedIdx);

  // longest run of consecutive finished day indexes
  let maxStreak = 0;
  let run = 0;
  let prev = null;
  for (const idx of finishedIdx) {
    run = prev !== null && idx === prev + 1 ? run + 1 : 1;
    if (run > maxStreak) maxStreak = run;
    prev = idx;
  }

  // current streak: count back from today (grace: if today isn't finished yet,
  // anchor on yesterday so the streak doesn't break until a full day is missed)
  const cur = currentDay(now);
  let anchor = finishedSet.has(cur) ? cur : cur - 1;
  let currentStreak = 0;
  while (finishedSet.has(anchor)) {
    currentStreak += 1;
    anchor -= 1;
  }

  const fin = finishedIdx.map((i) => entries[i]); // ascending by idx
  const totalPoints = fin.reduce((s, e) => s + e.points, 0);
  const totalPossible = fin.reduce((s, e) => s + e.n, 0);

  // question-level tallies (over finished days)
  const wins = fin.reduce((s, e) => s + e.wins, 0);
  const halves = fin.reduce((s, e) => s + e.halves, 0);
  const losses = fin.reduce((s, e) => s + e.losses, 0);
  const totalQ = totalPossible;

  // best / worst day (by points; tie-break: earliest)
  let bestDay = null;
  let worstDay = null;
  for (const e of fin) {
    if (!bestDay || e.points > bestDay.points) bestDay = e;
    if (!worstDay || e.points < worstDay.points) worstDay = e;
  }

  // last-7 average (by recency = highest indexes)
  const recent = [...fin].sort((a, b) => b.idx - a.idx).slice(0, 7);
  const avg7 = recent.length ? recent.reduce((s, e) => s + e.points, 0) / recent.length : 0;

  const liveCount = fin.filter((e) => e.live).length;

  return {
    played: Object.keys(entries).length,
    finished: fin.length,
    onDate: liveCount,
    later: fin.length - liveCount,
    currentStreak,
    maxStreak,
    avg: fin.length ? totalPoints / fin.length : 0,
    avg7,
    best: fin.reduce((m, e) => Math.max(m, e.points), 0),
    bestDay: bestDay ? { idx: bestDay.idx, points: bestDay.points, n: bestDay.n } : null,
    worstDay: worstDay ? { idx: worstDay.idx, points: worstDay.points, n: worstDay.n } : null,
    perfect: fin.filter((e) => e.points === e.n).length,
    totalPoints,
    totalPossible,
    totalQ,
    wins,
    halves,
    losses,
    days: fin.map((e) => ({ idx: e.idx, points: e.points, n: e.n, cells: e.cells, live: e.live })),
    finishedIdx,
  };
}
