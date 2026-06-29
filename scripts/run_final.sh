#!/bin/bash
# Final assembly, 26+ ONLY. Days -1..25 are already RELEASED and must NOT change
# (no locked rebuild, no apply_difficulty — both target the locked range).
# Compose 26+ from LLM-solvable candidates (actor/politics/blogger exclusions;
# adult/gambling are RE-INCLUDED per user), then finalize + verify.
# build_strict sets each composed puzzle's difficulty at compose time.
cd "$(dirname "$0")"
export PATH="$HOME/.local/node/bin:$PATH"
echo "===== [1/4] compose 26+ from solvable $(date +%H:%M:%S) ====="
python3 compose_days.py --start 26 --max-days 150 --seed 42 --sleep 0.4 || { echo COMPOSE FAIL; exit 1; }
echo "===== [2/4] gen_index $(date +%H:%M:%S) ====="
python3 gen_index.py || exit 1
echo "===== [3/4] check (DQ) $(date +%H:%M:%S) ====="
python3 check_days.py || echo "DQ reported issues"
echo "===== [4/4] build $(date +%H:%M:%S) ====="
cd ../app && npm run build 2>&1 | tail -6
echo "===== RUN_FINAL DONE $(date +%H:%M:%S) ====="
