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
        i = s.i ?? 0;
        results = s.results;
        done = !!s.done;
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
    <div class="card" class:shake={shaking} onanimationend={() => (shaking = false)}>
      <div class="dots">
        {#each results as r, k}
          <div class="dot" class:win={r === 'win'} class:half={r === 'half'} class:lose={r === 'lose'} class:cur={k === i}></div>
        {/each}
      </div>
      <div class="round">Раунд {i + 1} из {N}</div>
      <p class="lead">Статья дня относится к категориям:</p>
      <div class="cats">
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
        <div class="reveal">
          <div class="round">{revealLabel}</div>
          <div class="ans">{revealTitle}</div>
          <a href={revealWiki} target="_blank" rel="noopener">Открыть в Википедии ↗</a>
          {#if results[i] === 'half'}
            <div class="halfnote">🟨 Засчитано как ½ балла</div>
          {:else if canClaim && results[i] === 'lose'}
            <div class="subrow">
              <button class="link claim" onclick={claimRight}>Я всё-таки был прав 🟨 (½ балла)</button>
            </div>
          {/if}
          <div class="row"><button class="btn primary grow" onclick={next}>Дальше →</button></div>
        </div>
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
  :global(:root) {
    --bg: #0a0e1a; --card: #151d30; --card2: #1c2740; --text: #e7ecf5; --muted: #8b97b0;
    --accent: #1877f2; --green: #02e2ac; --orange: #f59e0b; --purple: #a855f7; --red: #ff5a7a;
    --border: #26324d; --shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
  }
  :global([data-theme='light']) {
    --bg: #eef2f9; --card: #ffffff; --card2: #f3f6fc; --text: #13203a; --muted: #5a6a86;
    --border: #dce3f0; --shadow: 0 10px 30px rgba(20, 40, 80, 0.1);
  }
  :global(body) {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    background: radial-gradient(1200px 600px at 50% -10%, rgba(24, 119, 242, 0.1), transparent), var(--bg);
    color: var(--text);
    min-height: 100vh;
    line-height: 1.5;
  }
  * { box-sizing: border-box; }
  .wrap { max-width: 680px; margin: 0 auto; padding: 20px 16px 64px; }
  header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
  .brand { display: flex; align-items: center; gap: 10px; font-weight: 800; font-size: 20px; }
  .fish { font-size: 24px; }
  .hgroup { display: flex; gap: 8px; align-items: center; }
  .day { color: var(--muted); font-size: 13px; font-weight: 600; }
  .iconbtn { background: var(--card); border: 1px solid var(--border); color: var(--text); border-radius: 10px; padding: 8px 10px; cursor: pointer; font-size: 16px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 20px; box-shadow: var(--shadow); }
  .dots { display: flex; gap: 6px; justify-content: center; margin: 0 0 14px; flex-wrap: wrap; }
  .dot { width: 22px; height: 10px; border-radius: 6px; background: var(--card2); border: 1px solid var(--border); }
  .dot.win { background: var(--green); border-color: var(--green); }
  .dot.half { background: var(--orange); border-color: var(--orange); }
  .dot.lose { background: var(--red); border-color: var(--red); opacity: 0.7; }
  .dot.cur { outline: 2px solid var(--accent); outline-offset: 1px; }
  .round { color: var(--muted); font-size: 13px; font-weight: 700; text-align: center; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.6px; }
  .lead { text-align: center; color: var(--muted); font-size: 14px; margin: 0 0 14px; }
  .cats { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin: 10px 0 4px; }
  .cat { background: var(--card2); border: 1px solid var(--border); border-radius: 999px; padding: 7px 13px; font-size: 14px; }
  .row { display: flex; gap: 8px; margin-top: 16px; }
  .row.center { justify-content: center; }
  .grow { flex: 1; }
  input[type='text'] { flex: 1; background: var(--bg); border: 1px solid var(--border); color: var(--text); border-radius: 12px; padding: 13px 14px; font-size: 16px; outline: none; }
  input[type='text']:focus { border-color: var(--accent); }
  .btn { border: none; border-radius: 12px; padding: 13px 16px; font-size: 15px; font-weight: 700; cursor: pointer; }
  .btn.primary { background: var(--accent); color: #fff; }
  .btn.ghost { background: var(--card2); color: var(--text); border: 1px solid var(--border); }
  .subrow { display: flex; gap: 8px; justify-content: center; margin-top: 10px; }
  .link { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 13px; text-decoration: underline; }
  .link.claim { color: var(--orange); font-weight: 700; }
  .halfnote { color: var(--orange); font-weight: 700; font-size: 14px; margin-top: 12px; }
  .feedback { min-height: 22px; text-align: center; margin-top: 12px; font-weight: 700; font-size: 14px; }
  .feedback.bad { color: var(--red); }
  .feedback.good { color: var(--green); }
  .reveal { margin-top: 14px; text-align: center; }
  .reveal .ans { font-size: 20px; font-weight: 800; margin: 6px 0; }
  .reveal a { color: var(--accent); text-decoration: none; font-size: 14px; }
  .tries { color: var(--muted); font-size: 12px; text-align: center; margin-top: 8px; }
  .shake { animation: shake 0.3s; }
  @keyframes shake { 0%, 100% { transform: translateX(0); } 25% { transform: translateX(-6px); } 75% { transform: translateX(6px); } }
  .end h2 { text-align: center; margin: 4px 0 2px; font-size: 26px; }
  .score { text-align: center; font-size: 40px; font-weight: 900; margin: 6px 0; }
  .grid { text-align: center; font-size: 26px; letter-spacing: 4px; margin: 10px 0; }
  .endlist { margin-top: 18px; }
  .endrow { display: flex; justify-content: space-between; gap: 10px; padding: 7px 0; border-top: 1px solid var(--border); font-size: 14px; }
  .foot { color: var(--muted); font-size: 12px; text-align: center; margin-top: 22px; }
  .foot a { color: var(--muted); }
</style>
