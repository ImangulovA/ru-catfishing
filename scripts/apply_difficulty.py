#!/usr/bin/env python3
"""Set/refresh the per-puzzle `difficulty` field on every dayN.json.

Reads the GLOBAL theme+tier map (prototype/data/_classified.json) and, for each
built day, decodes each puzzle's title from its base64 reveal and writes the
matching tier into `difficulty`. Only the `difficulty` field is touched;
categories / accept / reveal are left byte-for-byte intact.

Run AFTER classify_pool.py and after any day rebuild, so even locked/past days
show a difficulty consistent with the global percentiles.
"""
import base64
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAYS_DIR = os.path.join(ROOT, "app", "src", "lib", "days")
CLASSIFIED = os.path.join(ROOT, "prototype", "data", "_classified.json")


def reveal_title(b64):
    return base64.b64decode(b64).decode("utf-8")


def main():
    cls = json.load(open(CLASSIFIED, encoding="utf-8"))
    changed = 0
    missing = 0
    for f in sorted(glob.glob(os.path.join(DAYS_DIR, "day*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        dirty = False
        for p in d.get("puzzles", []):
            title = reveal_title(p["reveal"])
            meta = cls.get(title)
            tier = meta["tier"] if meta else "medium"
            if not meta:
                missing += 1
            if p.get("difficulty") != tier:
                p["difficulty"] = tier
                dirty = True
        if dirty:
            json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            changed += 1
    print(f"updated difficulty in {changed} day files; "
          f"{missing} puzzles had no classification (defaulted to medium)")


if __name__ == "__main__":
    main()
