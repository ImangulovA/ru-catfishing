#!/bin/bash
# Iteration 2: famous-only pool (pv>=5000) + expanded source (most-viewed) +
# canonical-pageviews fix. Locked days -1..25 keep their (current-norm) content;
# we re-classify, recompose 26+ from the famous pool, relabel difficulty, verify.
cd "$(dirname "$0")"
export PATH="$HOME/.local/node/bin:$PATH"

echo "===== [1/7] fetch_top most-viewed pool ($(date +%H:%M:%S)) ====="
python3 fetch_top.py || { echo "FETCH_TOP FAILED"; exit 1; }

echo "===== [2/7] evict redirect-undercounted famous titles from pv cache ====="
python3 - <<'PY'
import json, os
cache="../prototype/data/_pageviews_cache.json"
fam="../prototype/data/_famous.txt"
if os.path.exists(cache):
    c=json.load(open(cache,encoding='utf-8')); n0=len(c)
    if os.path.exists(fam):
        for line in open(fam,encoding='utf-8'):
            t=line.strip()
            if t and not t.startswith('#'):
                c.pop(t,None)
    json.dump(c,open(cache,'w',encoding='utf-8'),ensure_ascii=False)
    print(f'pv cache: {n0} -> {len(c)} (evicted famous)')
else:
    print('no pv cache yet')
PY

echo "===== [3/7] classify_pool (days + famous + most-viewed) ($(date +%H:%M:%S)) ====="
python3 classify_pool.py || { echo "CLASSIFY FAILED"; exit 1; }

echo "===== [4/7] compose famous balanced days 26+ ($(date +%H:%M:%S)) ====="
python3 compose_days.py --start 26 --seed 42 || { echo "COMPOSE FAILED"; exit 1; }

echo "===== [5/7] gen_index ($(date +%H:%M:%S)) ====="
python3 gen_index.py || exit 1

echo "===== [6/7] apply_difficulty (locked days) ($(date +%H:%M:%S)) ====="
python3 apply_difficulty.py || exit 1

echo "===== [7/7] DQ check + prod build ($(date +%H:%M:%S)) ====="
python3 check_days.py || echo "DQ CHECK reported failures (see above)"
cd ../app && npm run build 2>&1 | tail -8

echo ""
echo "===== PIPELINE2 DONE ($(date +%H:%M:%S)) ====="
