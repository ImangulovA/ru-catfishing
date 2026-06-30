<script>
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  let { children } = $props();

  // Apply the saved theme as early as possible so every route (game + archive)
  // is themed even on a direct visit. The header toggle (in +page) updates it.
  // Light is the default.
  onMount(() => {
    const t = localStorage.getItem('rucatfish_theme') || 'light';
    document.documentElement.dataset.theme = t;
  });
</script>

{@render children()}

<footer class="madeby">
  <a href="{base}/internals.html">
    <span class="ru">Как это сделано</span>
    <span class="en">How it was done</span>
  </a>
</footer>

<style>
  /* Global "making-of" footer, shown under every route. */
  footer.madeby {
    position: relative; z-index: 1;
    text-align: center;
    padding: 28px 16px 36px;
    border-top: 2px solid var(--line);
    margin-top: 32px;
  }
  footer.madeby a {
    display: inline-flex; flex-direction: column; gap: 2px;
    text-decoration: none; color: var(--text);
    font-weight: 800; font-size: 15px; letter-spacing: -0.2px;
    padding: 8px 16px; border: 2px solid var(--ink); border-radius: var(--radius-sm);
    background: var(--card2); box-shadow: var(--shadow-sm);
    transition: transform .08s ease, box-shadow .08s ease;
  }
  footer.madeby a:hover { transform: translate(-1px, -1px); box-shadow: 4px 4px 0 var(--ink); }
  footer.madeby a:active { transform: translate(2px, 2px); box-shadow: 1px 1px 0 var(--ink); }
  footer.madeby .en { font-weight: 600; font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }

  /* ============================================================
     NEOBRUTALISM design tokens — shared across all routes.
     default (:root) = warm light · [data-theme='dark'] = dark
     (light is :root so a no-JS / pre-hydration render is already light)
     ============================================================ */
  :global(:root) {
    --bg: #fbfbf9; --card: #ffffff; --card2: #fff8de; --field: #fbfbf9;
    --text: #1c293c; --muted: #5b667a;
    --accent: #fdc800; --accent-ink: #1c293c; --secondary: #432dd7;
    --green: #16a34a; --orange: #d97706; --red: #dc2626;
    --line: #1c293c; --ink: #1c293c;
    --radius: 10px; --radius-sm: 6px;
    --shadow: 5px 5px 0 var(--ink); --shadow-sm: 3px 3px 0 var(--ink);
    --font: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    --mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }
  :global([data-theme='dark']) {
    --bg: #12161d; --card: #1e2531; --card2: #262f3f; --field: #12161d;
    --text: #f4f5f7; --muted: #9aa6b8;
    --accent: #fdc800; --accent-ink: #14181f; --secondary: #8b72ff;
    --green: #22c55e; --orange: #f59e0b; --red: #f4365a;
    --line: #525e76;
    --ink: #000000;
  }
  :global(body) {
    margin: 0;
    font-family: var(--font);
    background-color: var(--bg);
    color: var(--text);
    min-height: 100vh;
    line-height: 1.5;
  }
  :global(body)::before {
    content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 0;
    background-image: radial-gradient(var(--line) 1px, transparent 1px);
    background-size: 24px 24px; opacity: 0.12;
  }
</style>
