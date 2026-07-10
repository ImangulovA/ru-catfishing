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
// Returns true if the send was at least dispatched, false otherwise.
//
// IMPORTANT: the body is sent as text/plain, NOT application/json. text/plain is
// a CORS-safelisted content type, so the cross-origin POST is a "simple request"
// with no preflight. navigator.sendBeacon CANNOT send preflighted requests and
// silently drops application/json beacons -> results never reach the Worker. The
// Worker parses the body with request.json() regardless of the Content-Type.
// Best-effort POST that AWAITS the Worker's response. Uses fetch with keepalive
// (survives page unload) and returns r.ok, so callers know the write actually
// landed (not just that it was queued). Previously this used navigator.sendBeacon
// and returned true the moment the beacon was queued -> results that never
// reached the Worker were still marked "sent", undercounting the global stats.
//
// IMPORTANT: the body is sent as text/plain, NOT application/json. text/plain is
// a CORS-safelisted content type, so the cross-origin POST is a "simple request"
// with no preflight. The Worker parses the body with request.json() regardless
// of the Content-Type.
async function post(path, payload) {
  if (!STATS_API || typeof fetch === 'undefined') return false;
  const url = STATS_API + path;
  try {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain' },
      body: JSON.stringify(payload),
      keepalive: true,
    });
    return r.ok;
  } catch (e) {
    return false;
  }
}

// Submit a finished day once. `points` may be fractional (halves) -> score2.
export async function submitResult(day, points, cells) {
  if (!STATS_API) return; // no backend yet -> don't mark sent, so it can backfill later
  const flag = 'rucatfish_sent_day' + day;
  const hasLS = typeof localStorage !== 'undefined';
  if (hasLS && localStorage.getItem(flag)) return; // already sent from this browser
  const sent = await post('/result', {
    day,
    score2: Math.round(points * 2),
    cells,
    clientId: clientId(),
  });
  // Only mark as sent once the Worker confirms (r.ok), so a transient failure
  // can still backfill on the next visit (the Worker dedupes by clientId+day,
  // so a retry never double-counts).
  if (sent && hasLS) localStorage.setItem(flag, '1');
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
