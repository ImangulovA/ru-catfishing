#!/bin/bash
# Full ru-catfishing rebuild: classify -> rebuild locked (-1..25, new norm) ->
# compose balanced 26+ -> gen_index -> apply difficulty -> DQ + prod build.
# Locked-day rebuilds are tolerant (one bad day must not abort the run); their
# failures are collected and printed at the end.
cd "$(dirname "$0")"
export PATH="$HOME/.local/node/bin:$PATH"
FAILED=""

echo "===== [1/6] classify_pool ($(date +%H:%M:%S)) ====="
python3 classify_pool.py || { echo "CLASSIFY FAILED"; exit 1; }

echo "===== [2/6] rebuild locked days -1..25 ($(date +%H:%M:%S)) ====="
for n in -1 0 1; do
  python3 make_day_from_txt.py $n || FAILED="$FAILED day$n"
done
python3 make_day.py 2 || FAILED="$FAILED day2"
for n in $(seq 3 25); do
  python3 make_day_from_txt.py $n || FAILED="$FAILED day$n"
done

echo "===== [3/6] compose balanced days 26+ ($(date +%H:%M:%S)) ====="
python3 compose_days.py --start 26 --seed 42 || { echo "COMPOSE FAILED"; exit 1; }

echo "===== [4/6] gen_index ($(date +%H:%M:%S)) ====="
python3 gen_index.py || exit 1

echo "===== [5/6] apply_difficulty ($(date +%H:%M:%S)) ====="
python3 apply_difficulty.py || exit 1

echo "===== [6/6] DQ check + prod build ($(date +%H:%M:%S)) ====="
python3 check_days.py || echo "DQ CHECK reported failures (see above)"
cd ../app && npm run build 2>&1 | tail -20

echo ""
echo "===== PIPELINE DONE ($(date +%H:%M:%S)) ====="
[ -n "$FAILED" ] && echo "LOCKED REBUILD FAILURES:$FAILED" || echo "locked rebuild: all OK"
