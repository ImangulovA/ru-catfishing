// Player stats across all days, read from localStorage (rucatfish_day<N>).
// Used on the end screen and the archive calendar.
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
    entries[idx] = {
      idx,
      finished: !!saved.done || answered === results.length,
      points: wins + halves * 0.5,
      n: results.length,
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

  const fin = finishedIdx.map((i) => entries[i]);
  const totalPoints = fin.reduce((s, e) => s + e.points, 0);
  const totalPossible = fin.reduce((s, e) => s + e.n, 0);

  return {
    played: Object.keys(entries).length,
    finished: fin.length,
    currentStreak,
    maxStreak,
    avg: fin.length ? totalPoints / fin.length : 0,
    best: fin.reduce((m, e) => Math.max(m, e.points), 0),
    perfect: fin.filter((e) => e.points === e.n).length,
    totalPoints,
    totalPossible,
  };
}
