<script>
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { base } from '$app/paths';
  import { DAYS, resolveDay, currentDay, fmtDate, todayIndex } from '$lib/days';
  import { computeStats } from '$lib/stats';
  import { submitResult, submitOpen, fetchAgg } from '$lib/api';
  import { applyUnlockFromUrl } from '$lib/unlock';

  const MAX_TRIES = 1; // catfishing = one shot
  const CAT = '🐈';    // угадал
  const FISH = '🐟';   // мимо
  const HALF = '🐠';   // «я всё-таки прав» = ½
  const WOOHOO = 8;    // score >= this => confetti + WOOHOO banner + share badge

  let day = $state(null);          // resolved strict day json
  let dayIdx = $state(0);          // which day index we're playing
  let isToday = $state(true);      // false when playing an archived day
  let isFuture = $state(false);    // true when author mode is playing a not-yet-released day

  let view = $state('intro');      // 'intro' | 'game' | 'end'
  let i = $state(0);
  let results = $state([]);        // per puzzle: null | 'win' | 'lose' | 'half'
  let guesses = $state([]);        // per puzzle: null (нет данных) | '' (пропуск) | введённый текст
  let agg = $state(null);          // глобальная стата по дню (win/half/miss на загадку)
  let canClaim = $state(false);    // show "Я прав" after a wrong guess (not skip)
  let tries = $state(0);
  let done = $state(false);
  let guess = $state('');
  let feedback = $state('');
  let feedbackKind = $state('');   // '' | 'good' | 'bad'
  let revealed = $state(false);
  let revealLabel = $state('');
  let revealTitle = $state('');
  let revealWiki = $state('');
  let revealImg = $state('');
  let shaking = $state(false);
  let theme = $state('light');
  let copied = $state(false);
  let untilMidnight = $state('');
  let stats = $state(null);
  let confettiCanvas = $state(null);  // bound <canvas>, used for the WOOHOO celebration

  // time until the next local midnight (user's own timezone), minute precision
  function fmtUntilMidnight() {
    const now = new Date();
    const mid = new Date(now);
    mid.setHours(24, 0, 0, 0);
    const totalMin = Math.max(0, Math.ceil((mid - now) / 60000));
    const h = Math.floor(totalMin / 60);
    const m = totalMin % 60;
    return h > 0 ? `${h} ч ${m} мин` : `${m} мин`;
  }

  const N = $derived(day ? day.puzzles.length : 0);
  const KEY = $derived(day ? 'rucatfish_day' + day.day : '');
  const puzzle = $derived(day ? day.puzzles[i] : null);
  const wins = $derived(results.filter((r) => r === 'win').length);
  const halves = $derived(results.filter((r) => r === 'half').length);
  const points = $derived(wins + halves * 0.5);
  const scoreLabel = $derived(Number.isInteger(points) ? String(points) : points.toFixed(1));

  // result -> emoji; nulls (unanswered) render as a miss, but the grid is only
  // shown once the day is finished, so there are none by then.
  const cells = $derived(results.map((r) => (r === 'win' ? CAT : r === 'half' ? HALF : FISH)));
  // split into rows of 5 for the Wordle-style share block
  const emojiRows = $derived.by(() => {
    const rows = [];
    for (let k = 0; k < cells.length; k += 5) rows.push(cells.slice(k, k + 5).join(''));
    return rows;
  });

  // Function/stop words dropped from answers, symmetric on both sides, so
  // "the last of us" == "last of us" and "О дивный новый мир" == "дивный новый
  // мир". MUST stay in sync with STOPWORDS in scripts/make_day.py:norm().
  const STOPWORDS = new Set(['the', 'of', 'о', 'об', 'обо', 'и', 'а', 'но', 'в', 'во', 'на', 'не']);

  function norm(s) {
    // Typo-tolerant + word-order independent. MUST stay byte-identical to
    // norm() in scripts/make_day.py, or guesses won't hash to the shipped
    // accept hashes. (verified via /tmp parity test)
    return (s || '')
      .toLowerCase()
      .replace(/ё/g, 'е')
      .replace(/э/g, 'е')
      .replace(/й/g, 'и')
      .replace(/\([^)]*\)/g, ' ')
      .replace(/['’‘ʼ`]/g, '') // апострофы/кавычки -> ничего (д'арк -> дарк)
      .replace(/[^а-яa-z0-9 ]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .replace(/(.)\1+/g, '$1')
      .split(' ')
      .filter(Boolean)
      .filter((w) => !STOPWORDS.has(w)) // drop function/stop words symmetrically
      // singular/plural & case tolerance: drop a trailing Russian inflection
      // vowel/ь so "коала"=="коалы", "челюсть"=="челюсти", "окно"=="окна". Only
      // when the stem stays >=3 chars. MUST stay byte-identical to stem() in
      // scripts/make_day.py:norm().
      .map((w) => (w.length >= 4 && 'аеиоуыюяь'.includes(w[w.length - 1]) ? w.slice(0, -1) : w))
      .sort()
      .join(' '); // порядок слов не важен (Бергкамп Деннис == Деннис Бергкамп)
  }

  async function sha256(s) {
    const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
    return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
  }

  function b64decode(b64) {
    const bin = atob(b64);
    const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
    return new TextDecoder().decode(bytes);
  }

  function save() {
    // `live` = played on the puzzle's own date (drives "on the day vs later" stat)
    if (browser && KEY) localStorage.setItem(KEY, JSON.stringify({ i, results, guesses, done, live: isToday }));
  }

  // raw per-puzzle outcome for the stats backend ('win' | 'half' | 'miss')
  const rawCells = () => results.map((r) => (r === 'win' ? 'win' : r === 'half' ? 'half' : 'miss'));

  // count an answer's Wikipedia article being opened (best-effort, anonymous)
  function openWiki() {
    submitOpen(dayIdx, i);
  }

  function applyTheme(t) {
    theme = t;
    if (browser) {
      document.documentElement.dataset.theme = t;
      localStorage.setItem('rucatfish_theme', t);
    }
  }

  onMount(() => {
    applyTheme(localStorage.getItem('rucatfish_theme') || 'light');

    // author mode: ?unlock=<password> persists a flag that opens future days
    const unlocked = applyUnlockFromUrl();

    // pick the day from ?day=N (archive) or default to today; future days are
    // only reachable when unlocked
    const requested = new URLSearchParams(location.search).get('day');
    dayIdx = resolveDay(requested, new Date(), unlocked);
    isToday = dayIdx === currentDay();
    isFuture = dayIdx > todayIndex();
    day = DAYS[dayIdx];

    const n = day.puzzles.length;
    results = Array(n).fill(null);
    guesses = Array(n).fill(null); // null = нет данных (старые дни покажутся как раньше)
    const key = 'rucatfish_day' + day.day;
    try {
      const s = JSON.parse(localStorage.getItem(key));
      if (s && Array.isArray(s.results) && s.results.length === n) {
        results = s.results;
        if (Array.isArray(s.guesses) && s.guesses.length === n) guesses = s.guesses;
        const firstOpen = results.findIndex((r) => r === null);
        if (firstOpen === -1) {
          done = true;
          i = n - 1;
        } else {
          i = firstOpen;
          done = !!s.done;
        }
      }
    } catch (e) {}

    untilMidnight = fmtUntilMidnight();
    const timer = setInterval(() => { untilMidnight = fmtUntilMidnight(); }, 60000);

    // Enter also advances to the next puzzle on the answer screen.
    // The submit-Enter is stopped from reaching here (stopPropagation in the
    // input handler), so it can't both submit AND skip in one keypress; we also
    // ignore auto-repeat so holding Enter doesn't blow through puzzles.
    const onKey = (e) => {
      if (e.key !== 'Enter' || e.repeat || view !== 'game' || !revealed) return;
      if (e.target && e.target.tagName === 'BUTTON') return; // let the button's own Enter work
      e.preventDefault();
      next();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      clearInterval(timer);
      window.removeEventListener('keydown', onKey);
    };
  });

  function start() {
    if (done) {
      goEnd();
    } else {
      view = 'game';
      newPuzzle();
    }
  }

  // Transition to the end screen + fire the celebration on a great score.
  function goEnd() {
    stats = computeStats();
    view = 'end';
    // submit the finished day to the global-stats backend (idempotent: api.js
    // guards with a per-day localStorage flag, so resuming a done day won't dupe)
    submitResult(dayIdx, points, rawCells());
    // подтянуть глобальную стату по этому дню для показа «% угадавших» на загадку
    fetchAgg([dayIdx]).then((a) => {
      if (a && a.ok) agg = a;
    });
    if (points >= WOOHOO) celebrate();
  }

  // Bright self-contained confetti burst (no libs, no CDN). Spawns colourful
  // squares/circles that fall with a little gravity + spin, for ~3.5s.
  function celebrate() {
    if (!browser || !confettiCanvas) return;
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const canvas = confettiCanvas;
    const ctx = canvas.getContext('2d');
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const W = () => window.innerWidth;
    const H = () => window.innerHeight;
    canvas.width = W() * dpr;
    canvas.height = H() * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const colors = ['#FDC800', '#a855f7', '#02e2ac', '#1877F2', '#f43f5e', '#ff7a00'];
    const COUNT = Math.min(220, Math.round(W() / 4));
    const parts = [];
    for (let k = 0; k < COUNT; k++) {
      parts.push({
        x: Math.random() * W(),
        y: -20 - Math.random() * H() * 0.6,
        r: 6 + Math.random() * 9,
        c: colors[k % colors.length],
        vx: -2.4 + Math.random() * 4.8,
        vy: 2.5 + Math.random() * 4,
        rot: Math.random() * Math.PI,
        vrot: -0.25 + Math.random() * 0.5,
        rect: Math.random() < 0.55,
      });
    }
    const startT = performance.now();
    const DURATION = 3500;
    function frame(now) {
      const t = now - startT;
      ctx.clearRect(0, 0, W(), H());
      for (const p of parts) {
        p.x += p.vx;
        p.y += p.vy;
        p.vy += 0.05; // gravity
        p.vx *= 0.995;
        p.rot += p.vrot;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillStyle = p.c;
        if (t > DURATION - 600) ctx.globalAlpha = Math.max(0, (DURATION - t) / 600);
        if (p.rect) ctx.fillRect(-p.r / 2, -p.r / 2, p.r, p.r * 0.6);
        else {
          ctx.beginPath();
          ctx.arc(0, 0, p.r / 2, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();
      }
      if (t < DURATION) requestAnimationFrame(frame);
      else ctx.clearRect(0, 0, W(), H());
    }
    requestAnimationFrame(frame);
  }

  function newPuzzle() {
    guess = '';
    feedback = '';
    feedbackKind = '';
    revealed = false;
    canClaim = false;
    tries = 0;
    revealImg = '';
  }

  async function check() {
    const g = norm(guess);
    if (!g) return;
    const h = await sha256(g);
    if (puzzle.accept.includes(h)) {
      feedback = '✅ Верно!';
      feedbackKind = 'good';
      reveal('win', 'Это:');
      return;
    }
    tries += 1;
    if (tries >= MAX_TRIES) {
      reveal('lose', 'Не угадал. Правильный ответ:');
      canClaim = true;
    } else {
      feedback = `Не то, попробуй ещё (${MAX_TRIES - tries})`;
      feedbackKind = 'bad';
      shaking = false;
      requestAnimationFrame(() => (shaking = true));
    }
  }

  function reveal(result, label, typed = guess) {
    results[i] = result;
    guesses[i] = (typed || '').trim(); // '' = пропуск, иначе введённый игроком текст
    revealed = true;
    revealLabel = label;
    revealTitle = b64decode(puzzle.reveal);
    revealWiki = 'https://ru.wikipedia.org/wiki/' + encodeURIComponent(revealTitle.replace(/ /g, '_'));
    save();
    fetchImg(revealTitle);
  }

  async function fetchImg(title) {
    if (!browser) return;
    const want = title;
    try {
      const url =
        'https://ru.wikipedia.org/api/rest_v1/page/summary/' +
        encodeURIComponent(title.replace(/ /g, '_'));
      const r = await fetch(url);
      if (!r.ok) return;
      const j = await r.json();
      const src = j?.thumbnail?.source || j?.originalimage?.source || '';
      if (src && revealed && revealTitle === want) revealImg = src;
    } catch (e) {}
  }

  function claimRight() {
    results[i] = 'half';
    canClaim = false;
    save();
  }

  // отзачёт: зеркало к claimRight — после автозачёта (win) игрок может отозвать
  // («я не это имел в виду»): win -> miss (полный отзачёт, 0 баллов)
  function unclaim() {
    results[i] = 'lose';
    save();
  }

  // тир сложности показываем на экране ответа (не раньше — чтобы не подсказывать)
  const DIFF = { easy: '🟢 Лёгкий', medium: '🟡 Средний', hard: '🔴 Сложный' };
  const diffLabel = $derived(puzzle && puzzle.difficulty ? DIFF[puzzle.difficulty] : '');

  function next() {
    if (i < N - 1) {
      i += 1;
      save();
      newPuzzle();
    } else {
      done = true;
      save();
      goEnd();
    }
  }

  function shareUrl() {
    if (!browser) return 'imangulova.github.io/ru-catfishing';
    return (location.host + location.pathname).replace(/\/$/, '');
  }

  function share() {
    const badge = points >= WOOHOO ? ' 🎉 WOOHOO' : '';
    const txt = `${shareUrl()}\n#${dayIdx} - ${scoreLabel}/${N}${badge}\n${emojiRows.join('\n')}`;
    navigator.clipboard.writeText(txt).then(() => {
      copied = true;
      setTimeout(() => (copied = false), 1500);
    });
  }

  const wikiUrl = (t) => 'https://ru.wikipedia.org/wiki/' + encodeURIComponent((t || '').replace(/ /g, '_'));

  // склонение слова «игрок» по числу
  function playersWord(n) {
    const a = n % 100;
    const b = n % 10;
    if (a >= 11 && a <= 14) return 'игроков';
    if (b === 1) return 'игрок';
    if (b >= 2 && b <= 4) return 'игрока';
    return 'игроков';
  }

  // глобальная статистика по конкретной загадке (или null, если данных нет)
  function pctFor(k) {
    const p = agg && agg.puzzle && agg.puzzle[dayIdx] && agg.puzzle[dayIdx][k];
    if (!p) return null;
    const total = (p.win || 0) + (p.half || 0) + (p.miss || 0);
    if (!total) return null;
    return {
      total,
      winPct: Math.round((100 * (p.win || 0)) / total),
      halfPct: Math.round((100 * (p.half || 0)) / total),
    };
  }

  const endLine = $derived(
    points >= 9 ? 'Шпион среди нас 🕵️' : points >= 7 ? 'Отличный улов 🎣' : points >= 4 ? 'Неплохо!' : 'Рыбка сорвалась 🐟'
  );
</script>

<div class="wrap">
  <header>
    <div class="brand"><span class="fish">🐟</span> Русский Catfishing</div>
    <div class="hgroup">
      {#if day}<span class="day" class:future={isFuture} title={fmtDate(dayIdx)}>День {dayIdx}{#if isFuture} · превью{:else if !isToday} · архив{/if}</span>{/if}
      <a class="iconbtn" href="{base}/stats" title="Статистика">📊</a>
      <a class="iconbtn" href="{base}/archive" title="Архив">🗓️</a>
      <button class="iconbtn" onclick={() => applyTheme(theme === 'dark' ? 'light' : 'dark')} title="Тема">
        {theme === 'dark' ? '🌙' : '☀️'}
      </button>
    </div>
  </header>

  {#if !day}
    <div class="card"><p class="lead">Загрузка…</p></div>
  {:else if view === 'intro'}
    <div class="card">
      <div class="round">Как играть</div>
      <p class="lead">
        Тебе показывают список категорий Википедии, к которым относится статья. Угадай, что это за статья.
        Сегодня <b>{N}</b> загадок. <b>Одна попытка</b> на каждую.
      </p>
      {#if isFuture}<p class="archnote">🔓 Режим автора: будущий день <b>{fmtDate(dayIdx)}</b> (ещё не вышел).</p>{:else if !isToday}<p class="archnote">Ты играешь архивный день: <b>{fmtDate(dayIdx)}</b>.</p>{/if}
      <div class="row"><button class="btn primary grow" onclick={start}>Играть</button></div>
    </div>
  {:else if view === 'game'}
    <div class="card game" class:answered={revealed} class:shake={shaking} onanimationend={() => (shaking = false)}>
      <div class="dots">
        {#each results as r, k}
          <div class="dot" class:win={r === 'win'} class:half={r === 'half'} class:lose={r === 'lose'} class:cur={k === i}></div>
        {/each}
      </div>

      {#if revealed}
        <div class="answer" class:win={results[i] === 'win'} class:lose={results[i] === 'lose'} class:half={results[i] === 'half'}>
          <div class="answer-label">{revealLabel}</div>
          <div class="answer-body">
            {#if revealImg}
              <a class="thumb" href={revealWiki} target="_blank" rel="noopener" onclick={openWiki}>
                <img src={revealImg} alt={revealTitle} loading="lazy" />
              </a>
            {/if}
            <div class="answer-text">
              <a class="ans" href={revealWiki} target="_blank" rel="noopener" onclick={openWiki}>{revealTitle}</a>
              <a class="wikilink" href={revealWiki} target="_blank" rel="noopener" onclick={openWiki}>Открыть в Википедии ↗</a>
              {#if diffLabel}<div class="diffrow">Сложность: <b>{diffLabel}</b></div>{/if}
              {#if results[i] === 'half'}
                <div class="halfnote">🐠 Засчитано как ½ балла</div>
              {:else if canClaim && results[i] === 'lose'}
                <button class="link claim" onclick={claimRight}>Я всё-таки был прав 🐠 (½ балла)</button>
              {:else if results[i] === 'win'}
                <button class="link unclaim" onclick={unclaim}>Я не это имел в виду 🐟 (отозвать)</button>
              {/if}
            </div>
          </div>
        </div>
      {/if}

      {#if !revealed}
        <div class="round">Раунд {i + 1} из {N}</div>
        <p class="lead">Статья дня относится к категориям:</p>
      {:else}
        <div class="catlabel">Категории этой статьи</div>
      {/if}
      <div class="cats" class:small={revealed}>
        {#each puzzle.categories as cat}
          <span class="cat">{cat}</span>
        {/each}
      </div>

      {#if !revealed}
        <div class="row">
          <input
            type="text"
            bind:value={guess}
            placeholder="Название статьи…"
            autocomplete="off"
            onkeydown={(e) => {
              if (e.key !== 'Enter') return;
              e.stopPropagation(); // don't let this Enter reach the window "advance" listener
              check();
            }}
          />
          <button class="btn primary" onclick={check}>Угадать</button>
        </div>
        <div class="feedback {feedbackKind}">{feedback}</div>
        <div class="subrow">
          <button class="link" onclick={() => reveal('lose', 'Пропущено. Это:', '')}>Пропустить →</button>
        </div>
      {:else}
        <div class="row"><button class="btn primary grow" onclick={next}>Дальше →</button></div>
        <div class="enterhint">или нажми Enter</div>
      {/if}
    </div>
  {:else if view === 'end'}
    <div class="card end" class:bigwin={points >= WOOHOO}>
      {#if points >= WOOHOO}
        <div class="woohoo">🎉 WOOHOO! 🎉</div>
        <p class="woohoo-sub">{points === N ? 'Идеально! Все рыбки твои 🐈' : 'Огонь! Так держать 🔥'}</p>
      {/if}
      <h2>Готово!</h2>
      <div class="score">{scoreLabel} / {N}</div>
      <div class="grid">
        {#each emojiRows as row}<div>{row}</div>{/each}
      </div>
      <p class="lead">{endLine}</p>
      <div class="row center">
        <button class="btn primary" onclick={share}>{copied ? 'Скопировано ✓' : 'Поделиться результатом'}</button>
      </div>
      {#if stats && stats.finished > 0}
        <div class="stats">
          <div class="stat"><div class="snum">🔥 {stats.currentStreak}</div><div class="slbl">серия</div></div>
          <div class="stat"><div class="snum">{stats.finished}</div><div class="slbl">дней</div></div>
          <div class="stat"><div class="snum">{stats.avg.toFixed(1)}</div><div class="slbl">в среднем</div></div>
          <div class="stat"><div class="snum">{stats.best}</div><div class="slbl">рекорд</div></div>
        </div>
        <p class="archmore"><a class="archlink" href="{base}/stats">Вся статистика →</a> · <a class="archlink" href="{base}/archive">архив и календарь</a></p>
      {/if}
      {#if isToday}
        <p class="nextgame">Новая игра через {untilMidnight} <span class="muted">(если я не забью хер)</span></p>
      {:else}
        <p class="nextgame"><a class="archlink" href="{base}/">К сегодняшней игре →</a></p>
      {/if}
      <div class="endlist">
        {#each day.puzzles as p, k}
          {@const correct = b64decode(p.reveal)}
          {@const mine = guesses[k]}
          {@const st = pctFor(k)}
          <div class="endrow">
            <div class="er-head">
              <span class="er-emoji">{results[k] === 'win' ? CAT : results[k] === 'half' ? HALF : FISH}</span>
              <a class="er-title" href={wikiUrl(correct)} target="_blank" rel="noopener">{correct}</a>
            </div>
            {#if results[k] !== 'win' && mine != null}
              <div class="er-mine">
                {#if mine}Твой ответ: «{mine}»{:else}Пропущено{/if}
              </div>
            {/if}
            {#if st}
              <div class="er-comm">
                <div class="bar">
                  <span class="seg win" style="width:{st.winPct}%"></span>
                  <span class="seg half" style="width:{st.halfPct}%"></span>
                </div>
                <div class="er-comm-txt">
                  {st.winPct}% угадали{#if st.halfPct > 0} · ещё {st.halfPct}% ½{/if} · {st.total} {playersWord(st.total)}
                </div>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <div class="foot">
    Прототип · данные из <a href="https://ru.wikipedia.org" target="_blank" rel="noopener">Википедии</a> (GFDL) ·
    <a href="{base}/archive">архив дней</a>
  </div>

  <canvas class="confetti" bind:this={confettiCanvas} aria-hidden="true"></canvas>
</div>

<style>
  /* NEOBRUTALISM design tokens live in +layout.svelte (shared across routes) */
  .wrap { max-width: 680px; margin: 0 auto; padding: 22px 16px 72px; position: relative; }
  .wrap > * { position: relative; z-index: 1; }

  :global(a):focus-visible, .btn:focus-visible, .iconbtn:focus-visible,
  .link:focus-visible, input[type='text']:focus-visible {
    outline: 3px solid var(--secondary); outline-offset: 2px;
  }

  header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; gap: 8px; flex-wrap: wrap; }
  .brand { display: flex; align-items: center; gap: 10px; font-weight: 900; font-size: 21px; letter-spacing: -0.4px; }
  .fish { font-size: 24px; }
  .hgroup { display: flex; gap: 8px; align-items: center; margin-left: auto; }
  .day { font-family: var(--mono); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; background: var(--accent); color: var(--accent-ink); border: 2px solid var(--ink); border-radius: var(--radius-sm); padding: 5px 9px; box-shadow: var(--shadow-sm); white-space: nowrap; }
  .day.future { background: var(--secondary); color: #fff; }
  .iconbtn { display: inline-flex; align-items: center; justify-content: center; background: var(--card); border: 2px solid var(--ink); color: var(--text); border-radius: var(--radius-sm); padding: 7px 10px; cursor: pointer; font-size: 16px; box-shadow: var(--shadow-sm); transition: transform 0.06s ease, box-shadow 0.06s ease; text-decoration: none; }
  .iconbtn:hover { transform: translate(-1px, -1px); box-shadow: 4px 4px 0 var(--ink); }
  .iconbtn:active { transform: translate(2px, 2px); box-shadow: 1px 1px 0 var(--ink); }

  .card { background: var(--card); border: 2px solid var(--ink); border-radius: var(--radius); padding: 22px; box-shadow: var(--shadow); }

  .dots { display: flex; gap: 6px; justify-content: center; margin: 0 0 16px; flex-wrap: wrap; }
  .dot { width: 24px; height: 12px; border-radius: 3px; background: var(--card2); border: 2px solid var(--line); }
  .dot.win { background: var(--green); border-color: var(--ink); }
  .dot.half { background: var(--orange); border-color: var(--ink); }
  .dot.lose { background: var(--red); border-color: var(--ink); }
  .dot.cur { outline: 3px solid var(--accent); outline-offset: 2px; }

  .round { font-family: var(--mono); color: var(--muted); font-size: 12px; font-weight: 700; text-align: center; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 1px; }
  .lead { text-align: center; color: var(--text); font-size: 15px; margin: 0 0 14px; font-weight: 500; }
  .archnote { text-align: center; color: var(--muted); font-size: 13px; margin: -4px 0 14px; }

  .card.game { box-sizing: border-box; --gw: min(96vw, 1100px); width: var(--gw); margin-left: calc(50% - var(--gw) / 2); }

  .catlabel { font-family: var(--mono); color: var(--muted); font-size: 11px; font-weight: 700; text-align: center; margin: 4px 0 8px; text-transform: uppercase; letter-spacing: 1px; }

  .cats { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; align-items: stretch; margin: 14px 0 4px; transition: gap 0.25s ease; }
  .cat {
    background: var(--card2); border: 2px solid var(--ink); border-radius: var(--radius);
    padding: 16px 22px; font-size: clamp(15px, 1.7vw, 21px); font-weight: 700;
    line-height: 1.25; flex: 1 1 clamp(170px, 22vw, 260px); min-width: min(170px, 100%); max-width: 100%;
    overflow-wrap: anywhere; hyphens: none;
    display: flex; align-items: center; justify-content: center; text-align: center;
    box-shadow: var(--shadow-sm);
    transition: padding 0.25s ease, font-size 0.25s ease, box-shadow 0.25s ease, transform 0.06s ease;
  }
  .cats.small { gap: 8px; }
  .cats.small .cat {
    padding: 5px 11px; font-size: 13px; font-weight: 600; border-radius: var(--radius-sm);
    border-width: 2px; flex: 0 0 auto; min-width: 0; color: var(--muted);
    background: transparent; border-color: var(--line); box-shadow: none;
  }

  .answer { border: 2px solid var(--ink); background: var(--card2); border-radius: var(--radius); padding: 16px; margin: 2px 0 18px; box-shadow: var(--shadow); border-top: 8px solid var(--accent); }
  .answer.win { border-top-color: var(--green); }
  .answer.lose { border-top-color: var(--red); }
  .answer.half { border-top-color: var(--orange); }
  .answer-label { font-family: var(--mono); color: var(--muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }
  .answer-body { display: flex; gap: 16px; align-items: flex-start; }
  .thumb { flex: 0 0 auto; line-height: 0; }
  .thumb img { width: 120px; height: 120px; object-fit: cover; border-radius: var(--radius-sm); border: 2px solid var(--ink); box-shadow: var(--shadow-sm); display: block; }
  .answer-text { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
  .answer .ans { font-size: clamp(21px, 3vw, 30px); font-weight: 900; color: var(--text); text-decoration: none; line-height: 1.12; letter-spacing: -0.5px; }
  .answer .ans:hover { text-decoration: underline; text-decoration-thickness: 3px; }
  .answer .wikilink { background: var(--accent); color: var(--accent-ink); align-self: flex-start; text-decoration: none; font-size: 13px; font-weight: 800; border: 2px solid var(--ink); border-radius: var(--radius-sm); padding: 5px 10px; box-shadow: var(--shadow-sm); transition: transform 0.06s ease, box-shadow 0.06s ease; }
  .answer .wikilink:hover { transform: translate(-1px, -1px); box-shadow: 4px 4px 0 var(--ink); }
  .answer .wikilink:active { transform: translate(2px, 2px); box-shadow: 1px 1px 0 var(--ink); }
  .answer-text .claim, .answer-text .halfnote { align-self: flex-start; margin-top: 2px; }

  .row { display: flex; gap: 10px; margin-top: 16px; }
  .row.center { justify-content: center; }
  .grow { flex: 1; }
  input[type='text'] {
    flex: 1; min-width: 0; background: var(--field); border: 2px solid var(--ink); color: var(--text);
    border-radius: var(--radius); padding: 13px 14px; font-size: 16px; font-family: var(--font);
    font-weight: 500; outline: none; box-shadow: var(--shadow-sm);
    transition: box-shadow 0.08s ease, transform 0.08s ease;
  }
  input[type='text']::placeholder { color: var(--muted); }
  input[type='text']:focus { transform: translate(-1px, -1px); box-shadow: 4px 4px 0 var(--accent); }

  .btn {
    border: 2px solid var(--ink); border-radius: var(--radius); padding: 13px 18px;
    font-size: 15px; font-weight: 800; font-family: var(--font); cursor: pointer;
    box-shadow: var(--shadow-sm); transition: transform 0.06s ease, box-shadow 0.06s ease;
  }
  .btn:hover { transform: translate(-1px, -1px); box-shadow: 5px 5px 0 var(--ink); }
  .btn:active { transform: translate(2px, 2px); box-shadow: 1px 1px 0 var(--ink); }
  .btn.primary { background: var(--accent); color: var(--accent-ink); }

  .subrow { display: flex; gap: 8px; justify-content: center; margin-top: 12px; }
  .link { background: none; border: none; color: var(--secondary); cursor: pointer; font-size: 14px; font-weight: 700; text-decoration: underline; text-underline-offset: 3px; padding: 4px; }
  .link.claim { color: var(--orange); font-weight: 800; }
  .link.unclaim { color: var(--red); font-weight: 800; }
  .diffrow { font-size: 13px; color: var(--muted); font-weight: 600; margin-top: 2px; }
  .diffrow b { color: var(--text); font-weight: 800; }
  .halfnote { color: var(--orange); font-weight: 800; font-size: 14px; margin-top: 12px; }
  .feedback { min-height: 22px; text-align: center; margin-top: 12px; font-weight: 800; font-size: 14px; }
  .feedback.bad { color: var(--red); }
  .feedback.good { color: var(--green); }
  .enterhint { text-align: center; color: var(--muted); font-family: var(--mono); font-size: 11px; margin-top: 8px; text-transform: uppercase; letter-spacing: 1px; }

  .shake { animation: shake 0.3s; }
  @keyframes shake { 0%, 100% { transform: translateX(0); } 25% { transform: translateX(-6px); } 75% { transform: translateX(6px); } }

  .end h2 { text-align: center; margin: 4px 0 2px; font-size: 28px; font-weight: 900; letter-spacing: -0.5px; }
  .score { text-align: center; font-size: 44px; font-weight: 900; margin: 6px 0; letter-spacing: -1px; }
  .grid { text-align: center; font-size: 26px; line-height: 1.25; letter-spacing: 4px; margin: 10px 0; }
  .endlist { margin-top: 18px; }
  .endrow { display: flex; flex-direction: column; gap: 6px; padding: 11px 0; border-top: 2px solid var(--line); font-size: 14px; font-weight: 500; }
  .er-head { display: flex; align-items: baseline; gap: 8px; }
  .er-emoji { font-size: 16px; flex: 0 0 auto; }
  .er-title { font-weight: 800; color: var(--text); text-decoration: none; }
  .er-title:hover { text-decoration: underline; text-decoration-thickness: 2px; }
  .er-mine { font-size: 13px; color: var(--muted); padding-left: 26px; }
  .er-comm { padding-left: 26px; display: flex; flex-direction: column; gap: 4px; }
  .bar { display: flex; height: 8px; border: 2px solid var(--ink); border-radius: 999px; overflow: hidden; background: var(--card2); max-width: 320px; }
  .seg { display: block; height: 100%; }
  .seg.win { background: var(--green); }
  .seg.half { background: var(--orange); }
  .er-comm-txt { font-family: var(--mono); font-size: 11px; color: var(--muted); font-weight: 700; }
  .foot { color: var(--muted); font-size: 12px; text-align: center; margin-top: 24px; }
  .foot a { color: var(--secondary); font-weight: 600; }
  .nextgame { text-align: center; font-family: var(--mono); font-size: 13px; font-weight: 700; margin: 14px 0 0; }
  .nextgame .muted { color: var(--muted); font-weight: 500; }
  .archlink { color: var(--secondary); font-weight: 700; text-decoration: underline; }
  .archmore { text-align: center; margin: 10px 0 0; font-size: 13px; }

  /* ---------- WOOHOO celebration (score >= 8) ---------- */
  .confetti { position: fixed; inset: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 60; }
  .woohoo {
    text-align: center; font-weight: 900; font-size: clamp(30px, 8vw, 48px); letter-spacing: -1px;
    margin: 2px 0 6px; color: var(--accent-ink); background: var(--accent);
    border: 3px solid var(--ink); border-radius: var(--radius); box-shadow: var(--shadow); padding: 10px 14px;
    animation: woohoo-pop 0.6s cubic-bezier(0.18, 0.89, 0.32, 1.28) both, woohoo-wiggle 1.6s ease-in-out 0.6s infinite;
  }
  .woohoo-sub { text-align: center; font-weight: 800; font-size: 15px; margin: 0 0 8px; color: var(--secondary); }
  @keyframes woohoo-pop {
    0% { transform: scale(0.3) rotate(-8deg); opacity: 0; }
    60% { transform: scale(1.12) rotate(3deg); opacity: 1; }
    100% { transform: scale(1) rotate(0); opacity: 1; }
  }
  @keyframes woohoo-wiggle { 0%, 100% { transform: rotate(-1.5deg); } 50% { transform: rotate(1.5deg); } }
  .end.bigwin .score { color: var(--green); animation: score-pulse 1.2s ease-in-out infinite; }
  @keyframes score-pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.06); } }
  @media (prefers-reduced-motion: reduce) {
    .woohoo, .end.bigwin .score { animation: none; }
  }

  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 16px 0 0; }
  .stat { background: var(--card2); border: 2px solid var(--ink); border-radius: var(--radius-sm); padding: 10px 6px; text-align: center; box-shadow: var(--shadow-sm); }
  .snum { font-family: var(--mono); font-weight: 900; font-size: 19px; line-height: 1.1; }
  .slbl { font-size: 10px; color: var(--muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 3px; }

  /* ---------- MOBILE: shrink everything, hide categories on the answer screen ---------- */
  @media (max-width: 600px) {
    .wrap { padding: 14px 10px 56px; }
    .brand { font-size: 16px; gap: 7px; }
    .fish { font-size: 18px; }
    .day { font-size: 11px; padding: 4px 7px; }
    .iconbtn { padding: 6px 8px; font-size: 15px; }
    .card { padding: 14px; }
    .card.game { --gw: 96vw; }
    .dots { gap: 4px; margin-bottom: 12px; }
    .dot { width: 16px; height: 9px; }
    .round { font-size: 11px; }
    .lead { font-size: 13px; margin-bottom: 10px; }
    .cats { gap: 7px; margin: 10px 0 2px; }
    .cat { padding: 9px 10px; font-size: 14px; min-width: 0; flex: 1 1 calc(50% - 7px); border-radius: var(--radius-sm); }
    input[type='text'] { padding: 11px 12px; }
    .btn { padding: 11px 13px; font-size: 14px; }
    .answer { padding: 12px; }
    .answer .ans { font-size: clamp(18px, 6vw, 24px); }
    .answer .wikilink { font-size: 12px; }
    .end h2 { font-size: 23px; }
    .score { font-size: 34px; }
    .grid { font-size: 22px; letter-spacing: 3px; }
    .endrow { font-size: 13px; }
    .er-mine, .er-comm { padding-left: 22px; }
    /* answer screen: categories are noise on a small screen -> hide them */
    .game.answered .cats,
    .game.answered .catlabel { display: none; }
  }
  @media (max-width: 480px) {
    .answer-body { flex-direction: column; align-items: center; text-align: center; }
    .answer-text { align-items: center; }
    .answer .wikilink, .answer-text .claim, .answer-text .halfnote { align-self: center; }
    .thumb img { width: 150px; height: 150px; }
  }
</style>
