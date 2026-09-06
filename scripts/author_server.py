#!/usr/bin/env python3
"""Local authoring server for hand-written ru-catfishing days.

    python3 scripts/author_server.py        # then open http://127.0.0.1:8765

Serves scripts/author_ui.html and a small JSON API. All the delicate work —
category fetching/filtering, alias expansion, norm() + sha256 — stays in Python
and reuses the exact functions the automated pipeline used, so a hand-built day
hashes identically to a machine-built one. The browser only draws the UI.

Endpoints
    GET  /api/state             what exists on disk, where the calendar ends
    GET  /api/search?q=         ru.wiki title autocomplete
    GET  /api/lookup?title=     categories + suggested answers for one title
    GET  /api/drafts            authoring/drafts.json
    PUT  /api/drafts            overwrite it (the UI autosaves)
    POST /api/build             run build_from_drafts.py, return its output

Bound to 127.0.0.1 only. It writes to authoring/drafts.json and, via /api/build,
to app/src/lib/days/ — nothing else.
"""
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# The pipeline talks to ru.wiki over HTTPS; on a machine whose system CA bundle
# is stale this fails with CERTIFICATE_VERIFY_FAILED. certifi's bundle is a
# drop-in fix and costs nothing when the system store is already fine.
if "SSL_CERT_FILE" not in os.environ:
    try:
        import certifi

        os.environ["SSL_CERT_FILE"] = certifi.where()
    except ImportError:
        pass

from build_pool import (  # noqa: E402
    api_get,
    fetch_categories,
    fetch_langlink,
    fetch_redirects,
    flush_cats_cache,
    is_giveaway,
    is_service,
    resolve_title,
    title_tokens,
)
from bulk_build import is_military  # noqa: E402
from make_day import derive_surname, expand_forms, given_surname_form, norm  # noqa: E402
from build_from_drafts import (  # noqa: E402
    DRAFTS,
    MANUAL_FROM,
    MIN_CATEGORIES,
    PER_DAY,
    check_day,
    load_drafts,
)

ROOT = os.path.dirname(HERE)
DAYS_DIR = os.path.join(ROOT, "app", "src", "lib", "days")
UI = os.path.join(HERE, "author_ui.html")
# Day 0 = 2026-06-04, see app/src/lib/days/index.js.
ANCHOR = datetime.date(2026, 6, 4)
PORT = int(os.environ.get("AUTHOR_PORT", "8765"))


def day_date(idx):
    return (ANCHOR + datetime.timedelta(days=idx)).isoformat()


def existing_days():
    out = []
    for f in glob.glob(os.path.join(DAYS_DIR, "day*.json")):
        m = re.match(r"day(-?\d+)\.json$", os.path.basename(f))
        if m:
            out.append(int(m.group(1)))
    return sorted(out)


def state():
    days = existing_days()
    drafts = load_drafts()
    draft_days = sorted((int(k) for k in (drafts.get("days") or {})))
    ready = {}
    for k, day in (drafts.get("days") or {}).items():
        ready[k] = not check_day(int(k), day)
    last = max(days) if days else -1
    return {
        "built_days": days,
        "built_last": last,
        "built_last_date": day_date(last) if days else None,
        "draft_days": draft_days,
        "draft_ready": ready,
        "manual_from": MANUAL_FROM,
        "per_day": PER_DAY,
        "min_categories": MIN_CATEGORIES,
        "anchor": ANCHOR.isoformat(),
        "year_end_day": (datetime.date(ANCHOR.year, 12, 31) - ANCHOR).days,
    }


def search(q):
    data = api_get({
        "action": "query", "list": "search", "srsearch": q,
        "srlimit": "12", "srnamespace": "0",
    })
    return [h["title"] for h in data.get("query", {}).get("search", [])]


def lookup(title):
    """Everything the editor needs about one candidate answer.

    Mirrors bulk_build.build_strict, except nothing is rejected: a category the
    filters would have dropped comes back flagged instead, so the author sees
    why and can overrule it.
    """
    resolved = resolve_title(title)
    cats = fetch_categories(resolved)
    flush_cats_cache()
    tokens = title_tokens(re.sub(r"\([^)]*\)", " ", resolved))

    categories = []
    for c in sorted(cats):
        if is_service(c):
            reason = "служебная"
        elif is_giveaway(c, tokens):
            reason = "выдаёт ответ"
        elif resolved in c:
            reason = "заголовок целиком"
        else:
            reason = None
        categories.append({"cat": c, "auto_hide": reason is not None, "reason": reason})

    useful = [c["cat"] for c in categories if not c["auto_hide"]]

    # suggested accepted answers: the title, its short forms, the en-wiki name,
    # every redirect pointing here, and the bare surname for people
    answers = {resolved}
    en = fetch_langlink(resolved, "en")
    if en:
        answers.add(en)
    for red in fetch_redirects(resolved):
        answers.add(red)
    sn = derive_surname(resolved, useful)
    if sn:
        answers.add(sn)
    gsf = given_surname_form(resolved, useful)
    if gsf:
        answers.add(gsf)
    answers = sorted(a for a in answers if norm(a))

    return {
        "title": resolved,
        "input": title,
        "redirected": resolved != title,
        "categories": categories,
        "visible_count": len(useful),
        "accept": answers,
        "is_person": bool(sn),
        "military": is_military(resolved, useful),
        "wiki_url": "https://ru.wikipedia.org/wiki/" + urllib.parse.quote(resolved.replace(" ", "_")),
    }


def normalize_preview(answers):
    """What each accepted answer collapses to — the author's sanity check."""
    out = []
    for a in answers:
        forms = sorted({norm(f) for f in expand_forms(a) if norm(f)})
        out.append({"answer": a, "forms": forms})
    return out


def save_drafts(payload):
    os.makedirs(os.path.dirname(DRAFTS), exist_ok=True)
    tmp = DRAFTS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, DRAFTS)


def run_build(day=None):
    cmd = [sys.executable, os.path.join(HERE, "build_from_drafts.py")]
    if day is not None:
        cmd += ["--day", str(day)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    return {"ok": r.returncode == 0, "stdout": r.stdout, "stderr": r.stderr}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                with open(UI, encoding="utf-8") as fh:
                    return self._send(200, fh.read(), "text/html; charset=utf-8")
            if u.path == "/api/state":
                return self._json(state())
            if u.path == "/api/drafts":
                return self._json(load_drafts())
            if u.path == "/api/search":
                return self._json({"results": search(q.get("q", [""])[0])})
            if u.path == "/api/lookup":
                return self._json(lookup(q.get("title", [""])[0].strip()))
            if u.path == "/api/preview":
                return self._json({"preview": normalize_preview(q.get("a", []))})
            return self._json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001 — surface it in the UI, keep serving
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    def do_PUT(self):
        try:
            if urllib.parse.urlparse(self.path).path == "/api/drafts":
                save_drafts(self._body())
                return self._json({"ok": True, "state": state()})
            return self._json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    def do_POST(self):
        try:
            if urllib.parse.urlparse(self.path).path == "/api/build":
                body = self._body()
                res = run_build(body.get("day"))
                res["state"] = state()
                return self._json(res)
            return self._json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)


def main():
    st = state()
    print(f"дни на диске: {st['built_days'][0]}..{st['built_last']} "
          f"(последний = {st['built_last_date']})")
    print(f"ручные дни начинаются с {MANUAL_FROM}; до конца года нужен день "
          f"{st['year_end_day']}")
    print(f"\n  http://127.0.0.1:{PORT}\n")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
