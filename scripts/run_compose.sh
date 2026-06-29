#!/bin/bash
cd "$(dirname "$0")"
export PATH="$HOME/.local/node/bin:$PATH"
echo "===== compose (cap 150) $(date +%H:%M:%S) ====="
python3 compose_days.py --start 26 --max-days 150 --seed 42 --sleep 0.4 || { echo COMPOSE FAILED; exit 1; }
echo "===== gen_index $(date +%H:%M:%S) ====="
python3 gen_index.py || exit 1
echo "===== apply_difficulty $(date +%H:%M:%S) ====="
python3 apply_difficulty.py || exit 1
echo "===== check + build $(date +%H:%M:%S) ====="
python3 check_days.py || echo "DQ reported failures"
cd ../app && npm run build 2>&1 | tail -8
echo "===== COMPOSE_PIPE DONE $(date +%H:%M:%S) ====="
