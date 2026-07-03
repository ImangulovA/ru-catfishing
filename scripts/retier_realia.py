#!/usr/bin/env python3
"""Re-tier realia among THEMSELVES so they populate easy/medium/hard slots.

Global tiers are terciles over a pool dominated by high-pageview celebrities, so
realia (lower pv) almost all fall into "hard". This overrides the tier of every
realia title (from _realia_titles.json, playable: pv>=REALIA_FLOOR & >=4 cats) with
terciles computed over the REALIA distribution only, using the same difficulty
score. People keep their global tiers. Writes _classified.json in place.

  python3 retier_realia.py          # apply
  python3 retier_realia.py --dry    # preview counts only
"""
import json
import os
import sys

from classify import difficulty_score, assign_tiers

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "prototype", "data")
CLASSIFIED = os.path.join(DATA, "_classified.json")
REALIA = os.path.join(DATA, "_realia_titles.json")
REALIA_FLOOR = 3000


def main():
    dry = "--dry" in sys.argv
    cls = json.load(open(CLASSIFIED, encoding="utf-8"))
    realia = json.load(open(REALIA, encoding="utf-8"))
    playable = [t for t in realia
                if cls.get(t, {}).get("pv", 0) >= REALIA_FLOOR
                and cls.get(t, {}).get("n_cats", 0) >= 4]
    scores = [(t, difficulty_score(cls[t]["pv"], cls[t]["n_cats"])) for t in playable]
    tiers = assign_tiers(scores)  # terciles within realia only

    from collections import Counter
    before = Counter(cls[t]["tier"] for t in playable)
    after = Counter(tiers[t] for t in playable)
    print(f"realia playable: {len(playable)}")
    print(f"  before: {dict(before)}")
    print(f"  after : {dict(after)}")
    if dry:
        print("(dry run -- _classified.json not modified)")
        return
    for t, tier in tiers.items():
        cls[t]["tier"] = tier
    json.dump(cls, open(CLASSIFIED, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"re-tiered {len(tiers)} realia in {CLASSIFIED}")


if __name__ == "__main__":
    main()
