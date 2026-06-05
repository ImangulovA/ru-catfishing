<script>
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import day from '$lib/days/day1.json';

  const MAX_TRIES = 1; // catfishing = one shot
  const KEY = 'rucatfish_day' + day.day;
  const N = day.puzzles.length;

  let view = $state('intro');      // 'intro' | 'game' | 'end'
  let i = $state(0);
  let results = $state(Array(N).fill(null)); // null | 'win' | 'lose' | 'half'
  let canClaim = $state(false);    // show "Я прав" after a wrong guess (not skip)
  let tries = $state(0);
  let done = $state(false);
  let guess = $state('');
  let feedback = $state('');       // text
  let feedbackKind = $state('');   // '' | 'good' | 'bad'
  let revealed = $state(false);
  let revealLabel = $state('');
  let revealTitle = $state('');
  let revealWiki = $state('');
  let revealImg = $state('');     // thumbnail fetched from ru.wiki after reveal
  let shaking = $state(false);
  let theme = $state('dark');
  let copied = $state(false);

  const puzzle = $derived(day.puzzles[i]);
  const wins = $derived(results.filter((r) => r === 'win').length);
  const halves = $derived(results.filter((r) => r === 'half').length);
  const points = $derived(wins + halves * 0.5); // win = 1, "я прав" = 0.5
  const scoreLabel = $derived(Number.isInteger(points) ? String(points) : points.toFixed(1));
  const grid = $derived(results.map((r) => (r === 'win' ? '🟩' : r === 'half' ? '🟨' : '⬜')).join(''));

  function norm(s) {
    return (s || '')
      .toLowerCase()
      .replace(/ё/g, 'е')
      .replace(/\([^)]*\)/g, ' ')
      .replace(/[^а-яa-z0-9 ]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
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
    if (browser) localStorage.setItem(KEY, JSON.stringify({ i, results, done }));
  }

  function applyTheme(t) {
    theme = t;
    if (browser) {
      document.documentElement.dataset.theme = t;
      localStorage.setItem('rucatfish_theme', t);
    }
  }

  onMount(() => {
    applyTheme(localStorage.getItem('rucatfish_theme') || 'dark');
    try {
      const s = JSON.parse(localStorage.getItem(KEY));
      if (s && Array.isArray(s.results)) {
        results = s.results;
        // one try each: resume at the first UNanswered puzzle, never re-answer an
        // already-resolved one (e.g. after reloading on the reveal screen)
        const firstOpen = results.findIndex((r) => r === null);
        if (firstOpen === -1) {
          done = true;
          i = N - 1;
        } else {
          i = firstOpen;
          done = !!s.done;
        }
      }
    } catch (e) {}
  });

  function start() {
    if (done) {
      view = 'end';
    } else {
      view = 'game';
      newPuzzle();
    }
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
      canClaim = true; // player made a real guess -> can claim half credit
    } else {
      feedback = `Не то, попробуй ещё (${MAX_TRIES - tries})`;
      feedbackKind = 'bad';
      shaking = false;
      requestAnimationFrame(() => (shaking = true));
    }
  }

  function reveal(result, label) {
    results[i] = result;
    revealed = true;
    revealLabel = label;
    revealTitle = b64decode(puzzle.reveal);
    revealWiki = 'https://ru.wikipedia.org/wiki/' + encodeURIComponent(revealTitle.replace(/ /g, '_'));
    save();
    fetchImg(revealTitle);
  }

  // Title is already revealed at this point, so pulling the article thumbnail
  // from ru.wiki leaks nothing. Race-guarded: ignore if the player moved on.
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
    results[i] = 'half'; // honor system: my answer was right, give ½ credit
    canClaim = false;
    save();
  }

  function next() {
    if (i < N - 1) {
      i += 1;
      save();
      newPuzzle();
    } else {
      done = true;
      save();
      view = 'end';
    }
  }

  function share() {
    const url = browser ? location.href : '';
    const txt = `🐟 Русский Catfishing · день ${day.day}\n${grid}  ${scoreLabel}/${N}\n${url}`;
    navigator.clipboard.writeText(txt).then(() => {
      copied = true;
      setTimeout(() => (copied = false), 1500);
    });
  }

  function replay() {
    if (browser) localStorage.removeItem(KEY);
    i = 0;
    results = Array(N).fill(null);
    done = false;
    view = 'game';
    newPuzzle();
  }

  const endLine = $derived(
    points >= 9 ? 'Шпион среди нас 🕵️' : points >= 7 ? 'Отличный улов 🎣' : points >= 4 ? 'Неплохо!' : 'Рыбка сорвалась 🐟'
  );
</script>

<div class="wrap">
  <header>
    <div class="brand"><span class="fish">🐟</span> Русский Catfishing</div>
    <div class="hgroup">
      <span class="day">День {day.day}</span>
      <button class="iconbtn" onclick={() => applyTheme(theme === 'dark' ? 'light' : 'dark')} title="Тема">
        {theme === 'dark' ? '🌙' : '☀️'}
      </button>
    </div>
  </header>

  {#if view === 'intro'}
    <div class="card">
      <div class="round">Как играть</div>
      <p class="lead">
        Тебе показывают список категорий Википедии, к которым относится статья. Угадай, что это за статья.
        Сегодня <b>{N}</b> загадок. <b>Одна попытка</b> на каждую.
      </p>
      <div class="row"><button class="btn primary grow" onclick={start}>Играть</button></div>
    </div>
  {/if}

  {#if view === 'game'}
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
              <a class="thumb" href={revealWiki} target="_blank" rel="noopener">
                <img src={revealImg} alt={revealTitle} loading="lazy" />
              </a>
            {/if}
            <div class="answer-text">
              <a class="ans" href={revealWiki} target="_blank" rel="noopener">{revealTitle}</a>
              <a class="wikilink" href={revealWiki} target="_blank" rel="noopener">Открыть в Википедии ↗</a>
              {#if results[i] === 'half'}
                <div class="halfnote">🟨 Засчитано как ½ балла</div>
              {:else if canClaim && results[i] === 'lose'}
                <button class="link claim" onclick={claimRight}>Я всё-таки был прав 🟨 (½ балла)</button>
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
            onkeydown={(e) => e.key === 'Enter' && check()}
          />
          <button class="btn primary" onclick={check}>Угадать</button>
        </div>
        <div class="feedback {feedbackKind}">{feedback}</div>
        <div class="subrow">
          <button class="link" onclick={() => reveal('lose', 'Пропущено. Это:')}>Пропустить →</button>
        </div>
      {:else}
        <div class="row"><button class="btn primary grow" onclick={next}>Дальше →</button></div>
      {/if}
    </div>
  {/if}

  {#if view === 'end'}
    <div class="card end">
      <h2>Готово!</h2>
      <div class="score">{scoreLabel} / {N}</div>
      <div class="grid">{grid}</div>
      <p class="lead">{endLine}</p>
      <div class="row center">
        <button class="btn primary" onclick={share}>{copied ? 'Скопировано ✓' : 'Поделиться результатом'}</button>
        <button class="btn ghost" onclick={replay}>Заново</button>
      </div>
      <div class="endlist">
        {#each day.puzzles as p, k}
          <div class="endrow">
            <span>{results[k] === 'win' ? '🟩' : results[k] === 'half' ? '🟨' : '⬜'} {b64decode(p.reveal)}</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <div class="foot">
    Прототип · данные из <a href="https://ru.wikipedia.org" target="_blank" rel="noopener">Википедии</a> (GFDL) ·
    угадайка в духе catfishing (Sumana Harihareswara, 2006)
  </div>
</div>

<style>
  /* ============================================================
     NEOBRUTALISM design system
     - default (:root) = Neobrutalism Dark
     - [data-theme='light'] = Neobrutalism (warm light)
     The header toggle flips data-theme, switching between the two.
     Tokens mirror design/neobrutalism.md + design/neobrutalism-dark.md
     ============================================================ */
  :global(:root) {
    /* Neobrutalism Dark */
    --bg: #12161d; --card: #1e2531; --card2: #262f3f; --field: #12161d;
    --text: #f4f5f7; --muted: #9aa6b8;
    --accent: #fdc800; --accent-ink: #14181f; --secondary: #8b72ff;
    --green: #22c55e; --orange: #f59e0b; --red: #f4365a;
    --line: #525e76;        /* card/chip/input outlines (lighter than card) */
    --ink: #000000;         /* hard borders on CTAs + all hard shadows */
    --radius: 10px; --radius-sm: 6px;
    --shadow: 5px 5px 0 var(--ink); --shadow-sm: 3px 3px 0 var(--ink);
    --font: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    --mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }
  :global([data-theme='light']) {
    /* Neobrutalism (warm light) */
    --bg: #fbfbf9; --card: #ffffff; --card2: #fff8de; --field: #fbfbf9;
    --text: #1c293c; --muted: #5b667a;
    --accent: #fdc800; --accent-ink: #1c293c; --secondary: #432dd7;
    --green: #16a34a; --orange: #d97706; --red: #dc2626;
    --line: #1c293c; --ink: #1c293c;
  }
  :global(body) {
    margin: 0;
    font-family: var(--font);
    background-color: var(--bg);
    color: var(--text);
    min-height: 100vh;
    line-height: 1.5;
  }
  .wrap { max-width: 680px; margin: 0 auto; padding: 22px 16px 72px; position: relative; }
  /* faint dot grid overlay (neobrutalism texture) */
  :global(body)::before {
    content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 0;
    background-image: radial-gradient(var(--line) 1px, transparent 1px);
    background-size: 24px 24px; opacity: 0.12;
  }
  .wrap > * { position: relative; z-index: 1; }

  /* Focus visibility (WCAG 2.2) */
  :global(a):focus-visible, .btn:focus-visible, .iconbtn:focus-visible,
  .link:focus-visible, input[type='text']:focus-visible {
    outline: 3px solid var(--secondary); outline-offset: 2px;
  }

  header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
  .brand { display: flex; align-items: center; gap: 10px; font-weight: 900; font-size: 21px; letter-spacing: -0.4px; }
  .fish { font-size: 24px; }
  .hgroup { display: flex; gap: 8px; align-items: center; }
  .day { font-family: var(--mono); color: var(--text); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; background: var(--accent); color: var(--accent-ink); border: 2px solid var(--ink); border-radius: var(--radius-sm); padding: 5px 9px; box-shadow: var(--shadow-sm); }
  .iconbtn { background: var(--card); border: 2px solid var(--ink); color: var(--text); border-radius: var(--radius-sm); padding: 7px 10px; cursor: pointer; font-size: 16px; box-shadow: var(--shadow-sm); transition: transform 0.06s ease, box-shadow 0.06s ease; }
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

  /* Game card breaks out of the narrow .wrap to use (almost) the full screen.
     Full-bleed via margin (NOT transform) so it never collides with .shake. */
  .card.game { --gw: min(96vw, 1100px); width: var(--gw); margin-left: calc(50% - var(--gw) / 2); }

  .catlabel { font-family: var(--mono); color: var(--muted); font-size: 11px; font-weight: 700; text-align: center; margin: 4px 0 8px; text-transform: uppercase; letter-spacing: 1px; }

  .cats { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; align-items: stretch; margin: 14px 0 4px; transition: gap 0.25s ease; }
  .cat {
    background: var(--card2); border: 2px solid var(--ink); border-radius: var(--radius);
    padding: 16px 22px; font-size: clamp(16px, 2.2vw, 22px); font-weight: 700;
    line-height: 1.25; flex: 1 1 auto; min-width: 190px; max-width: 100%;
    display: flex; align-items: center; justify-content: center; text-align: center;
    box-shadow: var(--shadow-sm);
    transition: padding 0.25s ease, font-size 0.25s ease, box-shadow 0.25s ease, transform 0.06s ease;
  }
  /* After the answer the categories collapse to small reference chips */
  .cats.small { gap: 8px; }
  .cats.small .cat {
    padding: 5px 11px; font-size: 13px; font-weight: 600; border-radius: var(--radius-sm);
    border-width: 2px; flex: 0 0 auto; min-width: 0; color: var(--muted);
    background: transparent; border-color: var(--line); box-shadow: none;
  }

  /* Revealed answer, pinned to the top of the card */
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
  .answer .wikilink { color: var(--text); background: var(--accent); color: var(--accent-ink); align-self: flex-start; text-decoration: none; font-size: 13px; font-weight: 800; border: 2px solid var(--ink); border-radius: var(--radius-sm); padding: 5px 10px; box-shadow: var(--shadow-sm); transition: transform 0.06s ease, box-shadow 0.06s ease; }
  .answer .wikilink:hover { transform: translate(-1px, -1px); box-shadow: 4px 4px 0 var(--ink); }
  .answer .wikilink:active { transform: translate(2px, 2px); box-shadow: 1px 1px 0 var(--ink); }
  .answer-text .claim, .answer-text .halfnote { align-self: flex-start; margin-top: 2px; }
  @media (max-width: 480px) {
    .answer-body { flex-direction: column; align-items: center; text-align: center; }
    .answer-text { align-items: center; }
    .answer .wikilink, .answer-text .claim, .answer-text .halfnote { align-self: center; }
    .thumb img { width: 150px; height: 150px; }
  }

  .row { display: flex; gap: 10px; margin-top: 16px; }
  .row.center { justify-content: center; }
  .grow { flex: 1; }
  input[type='text'] {
    flex: 1; background: var(--field); border: 2px solid var(--ink); color: var(--text);
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
  .btn.ghost { background: var(--card); color: var(--text); }

  .subrow { display: flex; gap: 8px; justify-content: center; margin-top: 12px; }
  .link { background: none; border: none; color: var(--secondary); cursor: pointer; font-size: 14px; font-weight: 700; text-decoration: underline; text-underline-offset: 3px; padding: 4px; }
  .link.claim { color: var(--orange); font-weight: 800; }
  .halfnote { color: var(--orange); font-weight: 800; font-size: 14px; margin-top: 12px; }
  .feedback { min-height: 22px; text-align: center; margin-top: 12px; font-weight: 800; font-size: 14px; }
  .feedback.bad { color: var(--red); }
  .feedback.good { color: var(--green); }

  .shake { animation: shake 0.3s; }
  @keyframes shake { 0%, 100% { transform: translateX(0); } 25% { transform: translateX(-6px); } 75% { transform: translateX(6px); } }

  .end h2 { text-align: center; margin: 4px 0 2px; font-size: 28px; font-weight: 900; letter-spacing: -0.5px; }
  .score { text-align: center; font-size: 44px; font-weight: 900; margin: 6px 0; letter-spacing: -1px; }
  .grid { text-align: center; font-size: 26px; letter-spacing: 4px; margin: 10px 0; }
  .endlist { margin-top: 18px; }
  .endrow { display: flex; justify-content: space-between; gap: 10px; padding: 9px 0; border-top: 2px solid var(--line); font-size: 14px; font-weight: 500; }
  .foot { color: var(--muted); font-size: 12px; text-align: center; margin-top: 24px; }
  .foot a { color: var(--secondary); font-weight: 600; }
</style>
