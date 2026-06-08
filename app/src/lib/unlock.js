// "Author mode" gate: unlock playing FUTURE days early.
//
// This is OBFUSCATION, not security. Future days already ship in the static
// bundle (categories in plaintext, answers base64), so a determined visitor can
// read them from source regardless. The gate just keeps casual players from
// stumbling onto unreleased days, and lets you share early access via a link.
import { UNLOCK_PASSWORD } from './config';

const KEY = 'rucatfish_unlocked';

export function isUnlocked() {
  if (typeof localStorage === 'undefined') return false; // SSR / prerender
  return localStorage.getItem(KEY) === '1';
}

export function setUnlocked(on) {
  if (typeof localStorage === 'undefined') return;
  if (on) localStorage.setItem(KEY, '1');
  else localStorage.removeItem(KEY);
}

// Read `?unlock=<password>` from the current URL. If it matches, persist the
// unlock flag and strip the param from the address bar (keeping any other
// params, e.g. ?day=N). Returns the resulting unlocked state. Safe to call when
// already unlocked (no param needed) — it just returns the stored flag.
export function applyUnlockFromUrl() {
  if (typeof window === 'undefined') return false;
  const params = new URLSearchParams(location.search);
  const supplied = params.get('unlock');
  if (supplied !== null) {
    if (supplied === UNLOCK_PASSWORD) setUnlocked(true);
    params.delete('unlock');
    const qs = params.toString();
    const clean = location.pathname + (qs ? '?' + qs : '') + location.hash;
    history.replaceState(null, '', clean);
  }
  return isUnlocked();
}
