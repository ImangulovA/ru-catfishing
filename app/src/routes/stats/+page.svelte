<script>
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  import { DAYS, fmtDate } from '$lib/days';
  import { computeStats } from '$lib/stats';
  import { fetchAgg, statsEnabled } from '$lib/api';

  let theme = $state('light');
  let stats = $state(null);       // local (computeStats)
  let agg = $state(null);         // global (Worker) or null
  let loadingGlobal = $state(false);
  const hasApi = statsEnabled();

  function applyTheme(t) {
    theme = t;
    document.documentElement.dataset.theme = t;
    localStorage.setItem('rucatfish_theme', t);
  }

  function b64decode(b64) {
    try {
      const bin = atob(b64);
      const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
      return new TextDecoder().decode(bytes);
    } catch (e) {
      return '?';
    }
  }
  const title = (day, idx) => {
    const p = DAYS[day]?.puzzles?.[idx];
    return p ? b64decode(p.reveal) : '?';
  };

  const pct = (x) => (x == null ? '—' : Math.round(x * 100) + '%');
  const fmtPts = (p) => (Number.isInteger(p) ? String(p) : p % 1 === 0.5 ? Math.floor(p) + '½' : p.toFixed(1));

  // ---- derived global views (computed once agg + stats are present) ----
  // "Your best days relative to other players": topPct = share who beat you.
  const relDays = $derived.by(() => {
    if (!agg || !stats) return [];
    const rows = [];
    for (const d of stats.days) {
      const dist = agg.dist?.[d.idx];
      if (!dist) continue;
      const yours = Math.round(d.points * 2);
      let total = 0, better = 0, sum = 0;
      for (const [s2, cnt] of Object.entries(dist)) {
        const s = Number(s2);
        total += cnt; sum += s * cnt;
        if (s > yours) better += cnt;
      }
      if (total < 2) continue; // need others to compare against
      rows.push({ idx: d.idx, points: d.points, topPct: better / total, dayAvg: sum / (2 * total) });
    }
    return rows.sort((a, b) => a.topPct - b.topPct).slice(0, 10);
  });

  // Puzzles YOU solved that fewest other players got right.
  const rareWins = $derived.by(() => {
    if (!agg || !stats) return [];
    const rows = [];
    for (const d of stats.days) {
      const pz = agg.puzzle?.[d.idx];
      if (!pz) continue;
      d.cells.forEach((c, idx) => {
        if (c !== 'win') return;
        const r = pz[idx];
        if (!r) return;
        const tot = r.win + r.half + r.miss;
        if (tot < 3) return;
        rows.push({ day: d.idx, idx, rate: r.win / tot, t: title(d.idx, idx) });
      });
    }
    return rows.sort((a, b) => a.rate - b.rate).slice(0, 8);
  });

  // Global day averages -> easiest / hardest overall.
  const topEasy = $derived.by(() => {
    if (!agg?.avgByDay) return [];
    return Object.entries(agg.avgByDay)
      .map(([d, v]) => ({ idx: Number(d), avg: v.avg, n: v.n }))
      .filter((x) => x.n >= 3)
      .sort((a, b) => b.avg - a.avg)
      .slice(0, 5);
  });
  const topHard = $derived.by(() => {
    if (!agg?.avgByDay) return [];
    return Object.entries(agg.avgByDay)
      .map(([d, v]) => ({ idx: Number(d), avg: v.avg, n: v.n }))
      .filter((x) => x.n >= 3)
      .sort((a, b) => a.avg - b.avg)
      .slice(0, 5);
  });

  onMount(async () => {
    theme = localStorage.getItem('rucatfish_theme') || 'light';
    stats = computeStats();
    if (hasApi && stats && stats.finishedIdx.length) {
      loadingGlobal = true;
      agg = await fetchAgg(stats.finishedIdx);
      loadingGlobal = false;
    }
  });
</script>

<div class="wrap">
  <header>
    <a class="brand" href="{base}/"><span class="fish">🐟</span> Русский Catfishing</a>
    <div class="hgroup">
      <a class="iconbtn" href="{base}/archive" title="Архив">🗓️</a>
      <button class="iconbtn" onclick={() => applyTheme(theme === 'dark' ? 'light' : 'dark')} title="Тема">
        {theme === 'dark' ? '🌙' : '☀️'}
      </button>
    </div>
  </header>

  <div class="card">
    <div class="round">Статистика</div>

    {#if !stats || stats.finished === 0}
      <p class="lead">Ты ещё не закончил ни одного дня. Сыграй — и тут появятся цифры.</p>
      <div class="row center"><a class="btn primary" href="{base}/">Играть →</a></div>
    {:else}
      <!-- personal headline grid -->
      <div class="grid5">
        <div class="stat"><div class="snum">{stats.finished}</div><div class="slbl">дней сыграно</div></div>
        <div class="stat"><div class="snum">🔥 {stats.currentStreak}</div><div class="slbl">серия</div></div>
        <div class="stat"><div class="snum">{stats.maxStreak}</div><div class="slbl">макс. серия</div></div>
        <div class="stat"><div class="snum">{stats.avg.toFixed(1)}</div><div class="slbl">средний</div></div>
        <div class="stat"><div class="snum">{stats.best}</div><div class="slbl">рекорд</div></div>
      </div>

      <div class="subgrid">
        <div class="mini"><b>{stats.onDate}</b> в день · <b>{stats.later}</b> позже</div>
        <div class="mini"><b>{stats.avg7.toFixed(1)}</b> за последние 7</div>
        <div class="mini"><b>{stats.perfect}</b> идеальных (×{DAYS[stats.bestDay?.idx]?.puzzles.length || 10})</div>
      </div>

      <!-- answer breakdown -->
      <div class="bars">
        <div class="barlabel">{stats.totalQ} вопросов</div>
        <div class="bar">
          {#if stats.wins}<div class="seg win" style="flex:{stats.wins}" title="угадал">{stats.wins}</div>{/if}
          {#if stats.halves}<div class="seg half" style="flex:{stats.halves}" title="½">{stats.halves}</div>{/if}
          {#if stats.losses}<div class="seg miss" style="flex:{stats.losses}" title="мимо">{stats.losses}</div>{/if}
        </div>
        <div class="barkey">
          <span><b class="dotc win"></b> {pct(stats.wins / stats.totalQ)} угадал</span>
          <span><b class="dotc half"></b> {pct(stats.halves / stats.totalQ)} почти</span>
          <span><b class="dotc miss"></b> {pct(stats.losses / stats.totalQ)} мимо</span>
        </div>
      </div>

      {#if stats.bestDay}
        <div class="bw">
          <a class="bwcell good" href="{base}/?day={stats.bestDay.idx}">
            <span class="bwlbl">Лучший день</span>
            <span class="bwval">{fmtPts(stats.bestDay.points)}/{stats.bestDay.n}</span>
            <span class="bwsub">день {stats.bestDay.idx} · {fmtDate(stats.bestDay.idx)}</span>
          </a>
          <a class="bwcell bad" href="{base}/?day={stats.worstDay.idx}">
            <span class="bwlbl">Худший день</span>
            <span class="bwval">{fmtPts(stats.worstDay.points)}/{stats.worstDay.n}</span>
            <span class="bwsub">день {stats.worstDay.idx} · {fmtDate(stats.worstDay.idx)}</span>
          </a>
        </div>
      {/if}

      <!-- per-day score sparkbars -->
      <div class="spark">
        <div class="barlabel">По дням</div>
        <div class="sparkrow">
          {#each stats.days as d}
            <a class="sbar" href="{base}/?day={d.idx}" title={`день ${d.idx}: ${fmtPts(d.points)}/${d.n}`}>
              <span class="sfill" style="height:{Math.max(6, (d.points / d.n) * 100)}%"></span>
            </a>
          {/each}
        </div>
      </div>
    {/if}
  </div>

  <!-- GLOBAL (cross-player) section -->
  {#if stats && stats.finished > 0}
    {#if !hasApi}
      <div class="card note">
        <div class="round">Глобальная статистика</div>
        <p class="lead">Сравнение с другими игроками подключится, когда будет задеплоен бэкенд
        (<span class="mono">backend/README.md</span>). Сейчас показана только твоя локальная статистика.</p>
      </div>
    {:else if loadingGlobal}
      <div class="card note"><p class="lead">Загружаю глобальную статистику…</p></div>
    {:else if agg}
      <div class="card">
        <div class="round">Среди всех игроков</div>
        <div class="grid5 two">
          {#if agg.allTimeAvg != null}
            <div class="stat"><div class="snum">{agg.allTimeAvg.toFixed(1)}</div><div class="slbl">средний за всё время</div></div>
          {/if}
          <div class="stat"><div class="snum">{agg.totalOpens.toLocaleString('ru-RU')}</div><div class="slbl">открытий Википедии</div></div>
        </div>

        {#if relDays.length}
          <div class="seclabel">Дни, где ты обошёл больше всего игроков</div>
          <div class="tbl">
            {#each relDays as r}
              <a class="trow" href="{base}/?day={r.idx}">
                <span class="tday">{fmtDate(r.idx)}</span>
                <span class="ttop">топ {Math.max(1, Math.round(r.topPct * 100))}%</span>
                <span class="tsc">{fmtPts(r.points)}</span>
                <span class="tavg">сред. {r.dayAvg.toFixed(1)}</span>
              </a>
            {/each}
          </div>
        {/if}

        {#if rareWins.length}
          <div class="seclabel">Ты угадал, а другие — почти нет</div>
          <div class="tbl">
            {#each rareWins as r}
              <div class="trow">
                <span class="tttl">{r.t}</span>
                <span class="trate">{Math.round(r.rate * 100)}% игроков</span>
              </div>
            {/each}
          </div>
        {/if}

        {#if agg.topOpens?.length}
          <div class="seclabel">Чаще всего открывали в Википедии</div>
          <div class="tbl">
            {#each agg.topOpens.slice(0, 10) as o}
              <div class="trow">
                <span class="tttl">{title(o.day, o.idx)}</span>
                <span class="trate">{o.opens.toLocaleString('ru-RU')}</span>
              </div>
            {/each}
          </div>
        {/if}

        {#if topEasy.length && topHard.length}
          <div class="seclabel">Самые лёгкие и сложные дни</div>
          <div class="eh">
            <div class="ehcol">
              <div class="ehhead good">лёгкие</div>
              {#each topEasy as d}<a class="ehrow" href="{base}/?day={d.idx}"><span>{fmtDate(d.idx)}</span><b>{d.avg.toFixed(1)}</b></a>{/each}
            </div>
            <div class="ehcol">
              <div class="ehhead bad">сложные</div>
              {#each topHard as d}<a class="ehrow" href="{base}/?day={d.idx}"><span>{fmtDate(d.idx)}</span><b>{d.avg.toFixed(1)}</b></a>{/each}
            </div>
          </div>
        {/if}
      </div>
    {/if}
  {/if}

  <div class="foot">
    <a href="{base}/">← к сегодняшней игре</a> · <a href="{base}/archive">архив</a>
  </div>
</div>

<style>
  .wrap { max-width: 680px; margin: 0 auto; padding: 22px 16px 72px; position: relative; }
  .wrap > * { position: relative; z-index: 1; }

  header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; gap: 8px; }
  .brand { display: flex; align-items: center; gap: 10px; font-weight: 900; font-size: 21px; letter-spacing: -0.4px; color: var(--text); text-decoration: none; }
  .fish { font-size: 24px; }
  .hgroup { display: flex; gap: 8px; align-items: center; }
  .iconbtn { display: inline-flex; align-items: center; justify-content: center; background: var(--card); border: 2px solid var(--ink); color: var(--text); border-radius: var(--radius-sm); padding: 7px 10px; cursor: pointer; font-size: 16px; box-shadow: var(--shadow-sm); transition: transform 0.06s ease, box-shadow 0.06s ease; text-decoration: none; }
  .iconbtn:hover { transform: translate(-1px, -1px); box-shadow: 4px 4px 0 var(--ink); }

  .card { background: var(--card); border: 2px solid var(--ink); border-radius: var(--radius); padding: 22px; box-shadow: var(--shadow); margin-bottom: 18px; }
  .card.note { background: var(--card2); }
  .round { font-family: var(--mono); color: var(--muted); font-size: 12px; font-weight: 700; text-align: center; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px; }
  .lead { text-align: center; color: var(--text); font-size: 14px; margin: 0; font-weight: 500; }
  .mono { font-family: var(--mono); font-size: 12px; background: var(--field); padding: 1px 5px; border-radius: 4px; }
  .row { display: flex; gap: 10px; margin-top: 14px; } .row.center { justify-content: center; }
  .btn { border: 2px solid var(--ink); border-radius: var(--radius); padding: 12px 18px; font-size: 15px; font-weight: 800; cursor: pointer; box-shadow: var(--shadow-sm); text-decoration: none; }
  .btn.primary { background: var(--accent); color: var(--accent-ink); }

  .grid5 { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin: 0 0 14px; }
  .grid5.two { grid-template-columns: repeat(2, 1fr); }
  .stat { background: var(--card2); border: 2px solid var(--ink); border-radius: var(--radius-sm); padding: 12px 4px; text-align: center; box-shadow: var(--shadow-sm); }
  .snum { font-family: var(--mono); font-weight: 900; font-size: 20px; line-height: 1.1; }
  .slbl { font-size: 9px; color: var(--muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; margin-top: 4px; }

  .subgrid { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-bottom: 16px; }
  .mini { background: var(--field); border: 2px solid var(--line); border-radius: var(--radius-sm); padding: 6px 10px; font-size: 12px; color: var(--muted); }
  .mini b { color: var(--text); font-family: var(--mono); }

  .bars { margin: 4px 0 16px; }
  .barlabel { font-family: var(--mono); font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
  .bar { display: flex; gap: 3px; height: 30px; }
  .seg { display: flex; align-items: center; justify-content: center; font-family: var(--mono); font-weight: 800; font-size: 12px; color: #fff; border: 2px solid var(--ink); border-radius: var(--radius-sm); min-width: 22px; }
  .seg.win { background: var(--green); } .seg.half { background: var(--orange); } .seg.miss { background: var(--red); }
  .barkey { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-top: 8px; font-size: 12px; color: var(--muted); }
  .dotc { display: inline-block; width: 10px; height: 10px; border: 2px solid var(--ink); border-radius: 3px; vertical-align: middle; }
  .dotc.win { background: var(--green); } .dotc.half { background: var(--orange); } .dotc.miss { background: var(--red); }

  .bw { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }
  .bwcell { display: flex; flex-direction: column; gap: 2px; padding: 12px; border: 2px solid var(--ink); border-radius: var(--radius-sm); box-shadow: var(--shadow-sm); text-decoration: none; color: var(--text); }
  .bwcell.good { border-top: 6px solid var(--green); } .bwcell.bad { border-top: 6px solid var(--red); }
  .bwlbl { font-family: var(--mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); font-weight: 700; }
  .bwval { font-size: 22px; font-weight: 900; font-family: var(--mono); }
  .bwsub { font-size: 11px; color: var(--muted); }

  .spark { margin-top: 4px; }
  .sparkrow { display: flex; gap: 3px; align-items: flex-end; height: 60px; padding: 4px; background: var(--field); border: 2px solid var(--line); border-radius: var(--radius-sm); overflow-x: auto; }
  .sbar { flex: 1 0 8px; min-width: 8px; height: 100%; display: flex; align-items: flex-end; }
  .sfill { width: 100%; background: var(--accent); border: 1px solid var(--ink); border-radius: 2px; }

  .seclabel { font-family: var(--mono); font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin: 18px 0 8px; }
  .tbl { display: flex; flex-direction: column; gap: 4px; }
  .trow { display: flex; align-items: center; gap: 8px; padding: 8px 10px; background: var(--card2); border: 2px solid var(--line); border-radius: var(--radius-sm); text-decoration: none; color: var(--text); font-size: 13px; }
  a.trow:hover { border-color: var(--ink); }
  .tday { flex: 1; font-weight: 600; }
  .ttop { font-family: var(--mono); font-weight: 800; color: var(--secondary); }
  .tsc { font-family: var(--mono); font-weight: 800; min-width: 28px; text-align: right; }
  .tavg { font-family: var(--mono); font-size: 11px; color: var(--muted); min-width: 64px; text-align: right; }
  .tttl { flex: 1; font-weight: 600; }
  .trate { font-family: var(--mono); font-weight: 800; color: var(--secondary); white-space: nowrap; }

  .eh { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .ehcol { display: flex; flex-direction: column; gap: 4px; }
  .ehhead { font-family: var(--mono); font-size: 11px; font-weight: 800; text-transform: uppercase; text-align: center; padding: 4px; border: 2px solid var(--ink); border-radius: var(--radius-sm); }
  .ehhead.good { background: var(--green); color: #fff; } .ehhead.bad { background: var(--red); color: #fff; }
  .ehrow { display: flex; justify-content: space-between; gap: 6px; padding: 6px 8px; background: var(--field); border: 2px solid var(--line); border-radius: var(--radius-sm); font-size: 12px; text-decoration: none; color: var(--text); }
  .ehrow b { font-family: var(--mono); }

  .foot { color: var(--muted); font-size: 13px; text-align: center; margin-top: 4px; }
  .foot a { color: var(--secondary); font-weight: 700; text-decoration: underline; }

  @media (max-width: 600px) {
    .wrap { padding: 14px 10px 56px; }
    .brand { font-size: 16px; } .fish { font-size: 18px; }
    .card { padding: 14px; }
    .grid5 { grid-template-columns: repeat(3, 1fr); }
    .snum { font-size: 17px; }
    .bw, .eh { grid-template-columns: 1fr; }
    .tavg { display: none; }
  }
</style>
