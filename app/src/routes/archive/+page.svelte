<script>
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  import { DAYS, availableDays, currentDay, dateForDay, fmtDate, todayIndex } from '$lib/days';
  import { computeStats } from '$lib/stats';
  import { isUnlocked } from '$lib/unlock';

  const CAT = '🐈', FISH = '🐟', HALF = '🐠';
  const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
  const MONTHS = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
  ];

  let months = $state([]);
  let stats = $state(null);
  let theme = $state('light');

  function applyTheme(t) {
    theme = t;
    document.documentElement.dataset.theme = t;
    localStorage.setItem('rucatfish_theme', t);
  }

  function readProgress(d) {
    const n = d.puzzles.length;
    let saved = null;
    try {
      saved = JSON.parse(localStorage.getItem('rucatfish_day' + d.day));
    } catch (e) {}
    if (!saved || !Array.isArray(saved.results)) {
      return { played: false, finished: false, score: '0', n };
    }
    const results = saved.results;
    const wins = results.filter((r) => r === 'win').length;
    const halves = results.filter((r) => r === 'half').length;
    const points = wins + halves * 0.5;
    const answered = results.filter((r) => r !== null).length;
    return {
      played: answered > 0,
      finished: !!saved.done || answered === n,
      score: Number.isInteger(points) ? String(points) : points.toFixed(1),
      n,
    };
  }

  function buildMonth(year, month, byKey) {
    const firstWeekday = (new Date(year, month, 1).getDay() + 6) % 7; // Mon = 0
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const cells = [];
    for (let i = 0; i < firstWeekday; i++) cells.push(null);
    for (let d = 1; d <= daysInMonth; d++) {
      cells.push({ d, info: byKey[`${year}-${month}-${d}`] || null });
    }
    while (cells.length % 7 !== 0) cells.push(null);
    const weeks = [];
    for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
    return { label: `${MONTHS[month]} ${year}`, weeks };
  }

  onMount(() => {
    theme = localStorage.getItem('rucatfish_theme') || 'light';
    stats = computeStats();

    const unlocked = isUnlocked(); // author mode: show future days too
    const tIdx = todayIndex();
    const cur = currentDay();
    const avail = availableDays(new Date(), unlocked); // indexes, newest first
    const byKey = {};
    for (const idx of avail) {
      const d = dateForDay(idx);
      byKey[`${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`] = {
        idx,
        isToday: idx === cur,
        isFuture: idx > tIdx,
        date: fmtDate(idx),
        ...readProgress(DAYS[idx]),
      };
    }

    // render every month from the earliest available day through the LAST one
    // (which is the current month normally, or a future month in author mode)
    const today = new Date();
    const start = avail.length ? dateForDay(Math.min(...avail)) : today;
    const last = avail.length ? dateForDay(Math.max(...avail)) : today;
    const list = [];
    let y = start.getFullYear();
    let m = start.getMonth();
    while (y < last.getFullYear() || (y === last.getFullYear() && m <= last.getMonth())) {
      list.push(buildMonth(y, m, byKey));
      m += 1;
      if (m > 11) { m = 0; y += 1; }
    }
    months = list;
  });
</script>

<div class="wrap">
  <header>
    <a class="brand" href="{base}/"><span class="fish">🐟</span> Русский Catfishing</a>
    <button class="iconbtn" onclick={() => applyTheme(theme === 'dark' ? 'light' : 'dark')} title="Тема">
      {theme === 'dark' ? '🌙' : '☀️'}
    </button>
  </header>

  <div class="card">
    <div class="round">Архив дней</div>
    <p class="lead">Каждый день — новые 10 загадок. Кликни на день, чтобы сыграть.</p>

    {#if stats && stats.finished > 0}
      <div class="stats">
        <div class="stat"><div class="snum">🔥 {stats.currentStreak}</div><div class="slbl">серия</div></div>
        <div class="stat"><div class="snum">{stats.maxStreak}</div><div class="slbl">макс. серия</div></div>
        <div class="stat"><div class="snum">{stats.finished}</div><div class="slbl">дней</div></div>
        <div class="stat"><div class="snum">{stats.avg.toFixed(1)}</div><div class="slbl">в среднем</div></div>
        <div class="stat"><div class="snum">{stats.best}</div><div class="slbl">рекорд</div></div>
      </div>
    {/if}

    {#each months as mo}
      <div class="month">
        <div class="month-label">{mo.label}</div>
        <div class="cal-head">
          {#each WEEKDAYS as w}<div class="wd">{w}</div>{/each}
        </div>
        {#each mo.weeks as week}
          <div class="cal-row">
            {#each week as cell}
              {#if !cell}
                <div class="cell empty"></div>
              {:else if cell.info}
                <a
                  class="cell has"
                  class:today={cell.info.isToday}
                  class:done={cell.info.finished}
                  class:future={cell.info.isFuture}
                  href={cell.info.isToday ? `${base}/` : `${base}/?day=${cell.info.idx}`}
                  title={`День ${cell.info.idx} · ${cell.info.date}${cell.info.isFuture ? ' · превью (ещё не вышел)' : ''}`}
                >
                  <span class="dt">{cell.d}</span>
                  {#if cell.info.finished}
                    <span class="sc">{cell.info.score}/{cell.info.n}</span>
                  {:else if cell.info.played}
                    <span class="sc dim">…</span>
                  {:else if cell.info.isFuture}
                    <span class="sc go">превью</span>
                  {:else}
                    <span class="sc go">играть</span>
                  {/if}
                </a>
              {:else}
                <div class="cell day"><span class="dt">{cell.d}</span></div>
              {/if}
            {/each}
          </div>
        {/each}
      </div>
    {/each}

    <div class="legend">
      <span><b class="chip today">сегодня</b></span>
      <span><b class="chip done">сыграно</b> — со счётом</span>
      <span><b class="chip go">играть</b> — ещё не пробовал</span>
    </div>
  </div>

  <div class="foot">
    <a href="{base}/">← к сегодняшней игре</a>
  </div>
</div>

<style>
  .wrap { max-width: 680px; margin: 0 auto; padding: 22px 16px 72px; position: relative; }
  .wrap > * { position: relative; z-index: 1; }

  header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; gap: 8px; }
  .brand { display: flex; align-items: center; gap: 10px; font-weight: 900; font-size: 21px; letter-spacing: -0.4px; color: var(--text); text-decoration: none; }
  .fish { font-size: 24px; }
  .iconbtn { display: inline-flex; align-items: center; justify-content: center; background: var(--card); border: 2px solid var(--ink); color: var(--text); border-radius: var(--radius-sm); padding: 7px 10px; cursor: pointer; font-size: 16px; box-shadow: var(--shadow-sm); transition: transform 0.06s ease, box-shadow 0.06s ease; }
  .iconbtn:hover { transform: translate(-1px, -1px); box-shadow: 4px 4px 0 var(--ink); }
  .iconbtn:active { transform: translate(2px, 2px); box-shadow: 1px 1px 0 var(--ink); }

  .card { background: var(--card); border: 2px solid var(--ink); border-radius: var(--radius); padding: 22px; box-shadow: var(--shadow); }
  .round { font-family: var(--mono); color: var(--muted); font-size: 12px; font-weight: 700; text-align: center; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 1px; }
  .lead { text-align: center; color: var(--text); font-size: 15px; margin: 0 0 18px; font-weight: 500; }

  .stats { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin: 0 0 20px; }
  .stat { background: var(--card2); border: 2px solid var(--ink); border-radius: var(--radius-sm); padding: 10px 4px; text-align: center; box-shadow: var(--shadow-sm); }
  .snum { font-family: var(--mono); font-weight: 900; font-size: 18px; line-height: 1.1; }
  .slbl { font-size: 9px; color: var(--muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; margin-top: 3px; }

  .month { margin-bottom: 22px; }
  .month-label { font-family: var(--mono); font-weight: 800; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; text-align: center; margin-bottom: 10px; }
  .cal-head, .cal-row { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
  .cal-head { margin-bottom: 6px; }
  .cal-row { margin-bottom: 6px; }
  .wd { text-align: center; font-family: var(--mono); font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; }

  .cell { aspect-ratio: 1 / 1; border-radius: var(--radius-sm); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; }
  .cell.empty { background: transparent; }
  .cell.day { color: var(--muted); opacity: 0.45; }
  .cell.day .dt { font-size: 13px; font-weight: 600; }

  .cell.has {
    background: var(--card2); border: 2px solid var(--ink); color: var(--text);
    text-decoration: none; box-shadow: var(--shadow-sm); cursor: pointer;
    transition: transform 0.06s ease, box-shadow 0.06s ease;
  }
  .cell.has:hover { transform: translate(-1px, -1px); box-shadow: 4px 4px 0 var(--ink); }
  .cell.has:active { transform: translate(2px, 2px); box-shadow: 1px 1px 0 var(--ink); }
  .cell.has .dt { font-size: 15px; font-weight: 800; line-height: 1; }
  .cell.has .sc { font-family: var(--mono); font-size: 10px; font-weight: 700; line-height: 1; }
  .cell.has .sc.go { color: var(--secondary); }
  .cell.has .sc.dim { color: var(--muted); }
  .cell.has.done { background: var(--green); color: #fff; border-color: var(--ink); }
  .cell.has.done .sc { color: #fff; }
  .cell.has.today { border-color: var(--ink); border-top: 6px solid var(--accent); background: var(--accent); color: var(--accent-ink); }
  .cell.has.today .sc, .cell.has.today.done .sc { color: var(--accent-ink); }
  .cell.has.today.done { background: var(--accent); color: var(--accent-ink); }
  .cell.has.future { border-style: dashed; background: var(--card2); }
  .cell.has.future .dt { color: var(--secondary); }
  .cell.has.future .sc.go { color: var(--secondary); }

  .legend { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-top: 8px; font-size: 12px; color: var(--muted); }
  .legend .chip { display: inline-block; border: 2px solid var(--ink); border-radius: var(--radius-sm); padding: 1px 7px; font-weight: 800; font-size: 11px; box-shadow: var(--shadow-sm); }
  .legend .chip.today { background: var(--accent); color: var(--accent-ink); }
  .legend .chip.done { background: var(--green); color: #fff; }
  .legend .chip.go { background: var(--card2); color: var(--secondary); }

  .foot { color: var(--muted); font-size: 13px; text-align: center; margin-top: 20px; }
  .foot a { color: var(--secondary); font-weight: 700; text-decoration: underline; }

  @media (max-width: 600px) {
    .wrap { padding: 14px 10px 56px; }
    .brand { font-size: 16px; }
    .fish { font-size: 18px; }
    .card { padding: 14px; }
    .cal-head, .cal-row { gap: 4px; }
    .cell.has .dt { font-size: 13px; }
    .cell.has .sc { font-size: 9px; }
    .legend { gap: 8px; }
    .stats { gap: 5px; }
    .stat { padding: 8px 2px; }
    .snum { font-size: 14px; }
    .slbl { font-size: 8px; }
  }
</style>
