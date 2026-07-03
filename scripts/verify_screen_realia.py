#!/usr/bin/env python3
"""Verify the realia solvability-swarm guesses and MERGE the solvable ones into
_solvable.json (union -- never drops the already-screened people).

Inputs:
  /tmp/screen_realia/map.json      [{id, title, theme, tier}]
  /tmp/screen_realia/batch_*.txt   id TAB categories
  /tmp/screen_realia/guesses.json  {id(str): guess}
Output (in place, unioned):
  prototype/data/_solvable.json
"""
import glob
import json
import os

from make_day import norm, expand_forms, derive_surname, given_surname_form

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCR = "/tmp/screen_realia"
OUT = os.path.join(ROOT, "prototype", "data", "_solvable.json")


def load_cats():
    cats = {}
    for f in glob.glob(os.path.join(SCR, "batch_*.txt")):
        for line in open(f, encoding="utf-8"):
            if "\t" not in line:
                continue
            i, c = line.rstrip("\n").split("\t", 1)
            cats[int(i)] = c.split(" | ")
    return cats


def accept_set(title, cats):
    forms = {norm(f) for f in expand_forms(title)}
    sn = derive_surname(title, cats)
    if sn:
        forms.add(norm(sn))
    gsf = given_surname_form(title, cats)
    if gsf:
        forms.add(norm(gsf))
    forms.discard("")
    return forms


def main():
    rows = json.load(open(os.path.join(SCR, "map.json"), encoding="utf-8"))
    cats = load_cats()
    guesses = {int(k): v for k, v in
               json.load(open(os.path.join(SCR, "guesses.json"), encoding="utf-8")).items()}

    existing = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else []
    solvable_new, total = [], 0
    by_theme = {}
    for r in rows:
        total += 1
        g = guesses.get(r["id"], "")
        ok = bool(g) and norm(g) in accept_set(r["title"], cats.get(r["id"], []))
        by_theme.setdefault(r["theme"], [0, 0])
        by_theme[r["theme"]][1] += 1
        if ok:
            solvable_new.append(r["title"])
            by_theme[r["theme"]][0] += 1

    merged = sorted(set(existing) | set(solvable_new))
    json.dump(merged, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"realia solvable {len(solvable_new)}/{total}; "
          f"_solvable.json {len(existing)} -> {len(merged)} (+{len(merged)-len(existing)})")
    for th, (s, t) in sorted(by_theme.items(), key=lambda kv: -kv[1][1]):
        print(f"  {th:11} {s}/{t}  ({100*s//max(t,1)}%)")


if __name__ == "__main__":
    main()
