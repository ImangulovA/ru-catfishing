<script>
  import { onMount } from 'svelte';
  let { children } = $props();

  // Apply the saved theme as early as possible so every route (game + archive)
  // is themed even on a direct visit. The header toggle (in +page) updates it.
  onMount(() => {
    const t = localStorage.getItem('rucatfish_theme') || 'dark';
    document.documentElement.dataset.theme = t;
  });
</script>

{@render children()}

<style>
  /* ============================================================
     NEOBRUTALISM design tokens — shared across all routes.
     default (:root) = Dark · [data-theme='light'] = warm light
     ============================================================ */
  :global(:root) {
    --bg: #12161d; --card: #1e2531; --card2: #262f3f; --field: #12161d;
    --text: #f4f5f7; --muted: #9aa6b8;
    --accent: #fdc800; --accent-ink: #14181f; --secondary: #8b72ff;
    --green: #22c55e; --orange: #f59e0b; --red: #f4365a;
    --line: #525e76;
    --ink: #000000;
    --radius: 10px; --radius-sm: 6px;
    --shadow: 5px 5px 0 var(--ink); --shadow-sm: 3px 3px 0 var(--ink);
    --font: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    --mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }
  :global([data-theme='light']) {
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
  :global(body)::before {
    content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 0;
    background-image: radial-gradient(var(--line) 1px, transparent 1px);
    background-size: 24px 24px; opacity: 0.12;
  }
</style>
