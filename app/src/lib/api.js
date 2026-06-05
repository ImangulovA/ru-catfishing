// Thin client for the global-stats Worker. Every call is best-effort and silent:
// if STATS_API is '' (not deployed yet) or the request fails, we no-op so the
// game and the local stats keep working.
import { STATS_API } from './config.js';

// A stable anonymous id, only to avoid double-counting a day server-side.
export function clientId() {
  if (typeof localStorage === 'undefined') return null;
  let id = localStorage.getItem('rucatfish_cid');
  if (!id) {
    id =
      (crypto?.randomUUID && crypto.randomUUID()) ||
      'c' + Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem('rucatfish_cid', id);
  }
  return id;
}

export const statsEnabled = () => !!STATS_API;

// Fire-and-forget POST. Uses sendBeacon when available (survives page unload).
function post(path, payload) {
  if (!STATS_API || typeof fetch === 'undefined') return;
  const url = STATS_API + path;
  try {
    const blob = JSON.stringify(payload);
    if (navigator?.sendBeacon) {
      navigator.sendBeacon(url, new Blob([blob], { type: 'application/json' }));
      return;
    }
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: blob,
      keepalive: true,
    }).catch(() => {});
  } catch (e) {}
}

// Submit a finished day once. `points` may be fractional (halves) -> score2.
export function submitResult(day, points, cells) {
  if (!STATS_API) return; // no backend yet -> don't mark sent, so it can backfill later
  if (typeof localStorage !== 'undefined') {
    const flag = 'rucatfish_sent_day' + day;
    if (localStorage.getItem(flag)) return; // already sent from this browser
    localStorage.setItem(flag, '1');
  }
  post('/result', {
    day,
    score2: Math.round(points * 2),
    cells,
    clientId: clientId(),
  });
}

export function submitOpen(day, idx) {
  post('/open', { day, idx });
}

// Fetch aggregates for the given played day indexes. Returns null on failure.
export async function fetchAgg(days) {
  if (!STATS_API || typeof fetch === 'undefined') return null;
  try {
    const q = encodeURIComponent((days || []).join(','));
    const r = await fetch(STATS_API + '/agg?days=' + q);
    if (!r.ok) return null;
    return await r.json();
  } catch (e) {
    return null;
  }
}
