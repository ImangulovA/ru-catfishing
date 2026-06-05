// Day registry + date mapping for ru-catfishing.
// Day 0 = 2026-06-04 (the original day1, shifted to "yesterday").
// Day 1 = 2026-06-05 (the new set), and so on, one puzzle-day per calendar day.
import day0 from './day0.json';
import day1 from './day1.json';
import day2 from './day2.json';
import day3 from './day3.json';

// index -> strict day json. Add new days here as they are built.
export const DAYS = { 0: day0, 1: day1, 2: day2, 3: day3 };

// Calendar anchor: day 0 falls on this local date.
const BASE = new Date(2026, 5, 4); // months are 0-based -> June 4, 2026
const MS_PER_DAY = 86400000;

function atMidnight(d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

// Which day index does "today" (the user's local date) correspond to?
export function todayIndex(now = new Date()) {
  return Math.round((atMidnight(now) - atMidnight(BASE)) / MS_PER_DAY);
}

// The calendar Date for a given day index.
export function dateForDay(n) {
  return new Date(atMidnight(BASE) + n * MS_PER_DAY);
}

const MONTHS = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
];

export function fmtDate(n) {
  const d = dateForDay(n);
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

// Day indexes that actually exist AND whose date has arrived (no spoilers from
// future days), newest first.
export function availableDays(now = new Date()) {
  const t = todayIndex(now);
  return Object.keys(DAYS)
    .map(Number)
    .filter((n) => n <= t)
    .sort((a, b) => b - a);
}

// The day to show by default: the latest available one (today, or the most
// recent built day if today's isn't built yet).
export function currentDay(now = new Date()) {
  const avail = availableDays(now);
  return avail.length ? avail[0] : 0;
}

// Resolve a requested ?day=N to a valid, available index (else the current day).
// NOTE: when there is no ?day param, `requested` is null/'' -> must fall back to
// the current day. (Number(null) === 0, so we can't let it reach the parse path,
// or every default visit would land on day 0.)
export function resolveDay(requested, now = new Date()) {
  if (requested === null || requested === undefined || requested === '') {
    return currentDay(now);
  }
  const n = Number(requested);
  if (Number.isInteger(n) && DAYS[n] && n <= todayIndex(now)) return n;
  return currentDay(now);
}
