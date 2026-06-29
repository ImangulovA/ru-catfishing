#!/usr/bin/env python3
"""Verify the solvability-swarm guesses and write the solvable-title set.

Inputs:
  /tmp/screen/map.json        [{id, title, theme, tier}]
  /tmp/screen/batch_*.txt      id TAB categories  (to derive surname/person forms)
  /tmp/screen/guesses.json     {id(str): guess}   (saved from the Workflow output)
Output:
  prototype/data/_solvable.json   sorted list of solvable titles
A candidate is "solvable" iff the blind LLM guess, normalised, matches the title's
core form (expand_forms), its surname, or its given+surname (no patronymic).
"""
import glob
import json
import os
import re
import sys

from make_day import norm, expand_forms, derive_surname, given_surname_form

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCR = "/tmp/screen"
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
    guesses = json.load(open(os.path.join(SCR, "guesses.json"), encoding="utf-8"))
    guesses = {int(k): v for k, v in guesses.items()}

    solvable, total = [], 0
    by_theme = {}
    for r in rows:
        total += 1
        g = guesses.get(r["id"], "")
        ok = bool(g) and norm(g) in accept_set(r["title"], cats.get(r["id"], []))
        by_theme.setdefault(r["theme"], [0, 0])
        by_theme[r["theme"]][1] += 1
        if ok:
            solvable.append(r["title"])
            by_theme[r["theme"]][0] += 1

    json.dump(sorted(solvable), open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"solvable {len(solvable)}/{total} -> {OUT}")
    for th, (s, t) in sorted(by_theme.items(), key=lambda kv: -kv[1][1]):
        print(f"  {th:11} {s}/{t}  ({100*s//max(t,1)}%)")


if __name__ == "__main__":
    main()
