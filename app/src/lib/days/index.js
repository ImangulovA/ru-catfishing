// Day registry + date mapping for ru-catfishing.
// Day 0 = 2026-06-04 (the original day1, shifted to "yesterday").
// Day 1 = 2026-06-05 (the new set), and so on, one puzzle-day per calendar day.
import day0 from './day0.json';
import day1 from './day1.json';
import day2 from './day2.json';
import day3 from './day3.json';
import day4 from './day4.json';
import day5 from './day5.json';
import day6 from './day6.json';
import day7 from './day7.json';
import day8 from './day8.json';
import day9 from './day9.json';
import day10 from './day10.json';
import day11 from './day11.json';
import day12 from './day12.json';
import day13 from './day13.json';
import day14 from './day14.json';
import day15 from './day15.json';
import day16 from './day16.json';
import day17 from './day17.json';
import day18 from './day18.json';
import day19 from './day19.json';
import day20 from './day20.json';
import day21 from './day21.json';
import day22 from './day22.json';
import day23 from './day23.json';

// index -> strict day json. Add new days here as they are built.
export const DAYS = {
  0: day0, 1: day1, 2: day2, 3: day3, 4: day4, 5: day5, 6: day6, 7: day7,
  8: day8, 9: day9, 10: day10, 11: day11, 12: day12, 13: day13, 14: day14,
  15: day15, 16: day16, 17: day17, 18: day18, 19: day19, 20: day20,
  21: day21, 22: day22, 23: day23,
};

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
