<script>
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  import { DAYS, availableDays, currentDay, fmtDate } from '$lib/days';

  const CAT = '🐈', FISH = '🐟', HALF = '🐠';

  let rows = $state([]);
  let theme = $state('dark');

  function applyTheme(t) {
    theme = t;
    document.documentElement.dataset.theme = t;
    localStorage.setItem('rucatfish_theme', t);
  }

  function readProgress(d) {
    // returns { played, finished, score, n, grid } for a day's strict json
    const n = d.puzzles.length;
    let saved = null;
    try {
      saved = JSON.parse(localStorage.getItem('rucatfish_day' + d.day));
    } catch (e) {}
    if (!saved || !Array.isArray(saved.results)) {
      return { played: false, finished: false, score: '0', n, grid: '' };
    }
    const results = saved.results;
    const wins = results.filter((r) => r === 'win').length;
    const halves = results.filter((r) => r === 'half').length;
    const points = wins + halves * 0.5;
    const answered = results.filter((r) => r !== null).length;
    const grid = results.map((r) => (r === 'win' ? CAT : r === 'half' ? HALF : r === null ? '·' : FISH)).join('');
    return {
      played: answered > 0,
      finished: !!saved.done || answered === n,
      score: Number.isInteger(points) ? String(points) : points.toFixed(1),
      n,
      grid,
    };
  }

  onMount(() => {
    theme = localStorage.getItem('rucatfish_theme') || 'dark';
    const cur = currentDay();
    rows = availableDays().map((idx) => ({
      idx,
      date: fmtDate(idx),
      isToday: idx === cur,
      ...readProgress(DAYS[idx]),
    }));
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
    <p class="lead">Каждый день — новые 10 загадок. Можно вернуться к прошлым дням.</p>

    <div class="list">
      {#each rows as r}
        <a class="dayrow" class:today={r.isToday} href={r.isToday ? `${base}/` : `${base}/?day=${r.idx}`}>
          <div class="left">
            <span class="num">#{r.idx}</span>
            <span class="date">{r.date}{#if r.isToday} · сегодня{/if}</span>
          </div>
          <div class="right">
            {#if r.finished}
              <span class="grid">{r.grid}</span>
              <span class="score">{r.score}/{r.n}</span>
            {:else if r.played}
              <span class="grid">{r.grid}</span>
              <span class="tag">продолжить →</span>
            {:else}
              <span class="tag play">играть →</span>
            {/if}
          </div>
        </a>
      {/each}
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
  .lead { text-align: center; color: var(--text); font-size: 15px; margin: 0 0 16px; font-weight: 500; }

  .list { display: flex; flex-direction: column; gap: 10px; }
  .dayrow {
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    background: var(--card2); border: 2px solid var(--ink); border-radius: var(--radius);
    padding: 12px 16px; text-decoration: none; color: var(--text);
    box-shadow: var(--shadow-sm); transition: transform 0.06s ease, box-shadow 0.06s ease;
  }
  .dayrow:hover { transform: translate(-1px, -1px); box-shadow: 4px 4px 0 var(--ink); }
  .dayrow:active { transform: translate(2px, 2px); box-shadow: 1px 1px 0 var(--ink); }
  .dayrow.today { border-top: 8px solid var(--accent); }
  .left { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .num { font-family: var(--mono); font-weight: 800; font-size: 16px; }
  .date { color: var(--muted); font-size: 13px; font-weight: 500; }
  .right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
  .right .grid { font-size: 15px; letter-spacing: 1px; }
  .score { font-family: var(--mono); font-weight: 800; font-size: 15px; background: var(--accent); color: var(--accent-ink); border: 2px solid var(--ink); border-radius: var(--radius-sm); padding: 3px 8px; box-shadow: var(--shadow-sm); }
  .tag { font-weight: 800; font-size: 13px; color: var(--secondary); }
  .tag.play { color: var(--accent-ink); background: var(--accent); border: 2px solid var(--ink); border-radius: var(--radius-sm); padding: 4px 9px; box-shadow: var(--shadow-sm); }

  .foot { color: var(--muted); font-size: 13px; text-align: center; margin-top: 24px; }
  .foot a { color: var(--secondary); font-weight: 700; text-decoration: underline; }

  @media (max-width: 600px) {
    .wrap { padding: 14px 10px 56px; }
    .brand { font-size: 16px; }
    .fish { font-size: 18px; }
    .card { padding: 14px; }
    .dayrow { padding: 10px 12px; }
    .right .grid { display: none; } /* keep rows compact on small screens */
  }
</style>
