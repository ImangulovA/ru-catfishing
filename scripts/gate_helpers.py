#!/usr/bin/env python3
"""Helpers for the LLM solvability gate (the assistant drives the LLM via the
Agent tool; these functions handle the deterministic parts).

Flow per day:
  1. day_categories(n)        -> feed categories (no answers) to an LLM player
  2. verify_day(n, guesses)   -> which puzzles the LLM did NOT solve
  3. pick_spares(theme,tier)  -> famous replacements (same theme+tier, unused)
  4. replace_puzzle(...)      -> rebuild + swap that one puzzle in the day json
  5. re-run the LLM on replacements; repeat until 10/10
"""
import base64
import glob
import hashlib
import json
import os
import random

from make_day import norm
from bulk_build import build_strict
from classify import is_excluded

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAYS = os.path.join(ROOT, "app", "src", "lib", "days")
CLASSIFIED = os.path.join(ROOT, "prototype", "data", "_classified.json")


def rt(b):
    return base64.b64decode(b).decode("utf-8")


def h(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def day_path(n):
    return os.path.join(DAYS, f"day{n}.json")


def day_categories(n):
    """[(idx, answer_title, categories[])] for a day (answer is for OUR check)."""
    d = json.load(open(day_path(n), encoding="utf-8"))
    return [(i, rt(p["reveal"]), p["categories"]) for i, p in enumerate(d["puzzles"])]


def verify_day(n, guesses):
    """guesses: {idx: guess_str}. Return [(idx, answer, theme?)] of MISSES."""
    d = json.load(open(day_path(n), encoding="utf-8"))
    cls = _cls()
    miss = []
    for i, p in enumerate(d["puzzles"]):
        g = guesses.get(i, "")
        if h(norm(g or "")) not in p["accept"]:
            ans = rt(p["reveal"])
            miss.append({"idx": i, "answer": ans, "tier": p.get("difficulty", "medium"),
                         "theme": cls.get(ans, {}).get("theme", "?")})
    return miss


_CLS = None


def _cls():
    global _CLS
    if _CLS is None:
        _CLS = json.load(open(CLASSIFIED, encoding="utf-8"))
    return _CLS


def all_used_keys():
    keys = set()
    for f in glob.glob(os.path.join(DAYS, "day*.json")):
        d = json.load(open(f, encoding="utf-8"))
        for p in d["puzzles"]:
            keys.add(norm(rt(p["reveal"])))
    return keys


def pick_spares(theme, tier, used_keys, k=6):
    """Famous (pv>=5000, >=4 cats) candidates of this theme+tier, not yet used."""
    cls = _cls()
    cands = [(m.get("pv", 0), t) for t, m in cls.items()
             if m.get("pv", 0) >= 5000 and m.get("n_cats", 0) >= 4
             and (theme is None or m.get("theme") == theme) and m.get("tier") == tier
             and norm(t) not in used_keys]
    # most-viewed first: famous spares are likelier to be solvable
    cands.sort(reverse=True)
    return [t for _pv, t in cands[:k]]


def replace_puzzle(n, idx, new_title, tier):
    """Rebuild new_title and swap it into day n at position idx. Returns the new
    puzzle's categories on success, or None if it failed the gate / is excluded."""
    strict, _, status = build_strict(new_title, tier)
    if status != "ok" or is_excluded(strict["categories"]):
        return None
    d = json.load(open(day_path(n), encoding="utf-8"))
    d["puzzles"][idx] = strict
    json.dump(d, open(day_path(n), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return strict["categories"]
