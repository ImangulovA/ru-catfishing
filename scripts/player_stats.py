#!/usr/bin/env python3
"""ru-catfishing — статистика по числу игроков за последние дни.

Тянет агрегаты из глобального стат-воркера (Cloudflare Worker + D1) через
endpoint /agg и считает, сколько человек сыграло каждый день.

Модель данных: на каждый (clientId, day) сервер пишет ровно одну запись
(идемпотентность в submissions). Значит avgByDay[day].n = число игроков,
завершивших этот день. Один человек, сыгравший несколько дней, считается в
каждом дне отдельно — глобального уникального счётчика людей бэкенд не хранит.

Запуск:
    python3 player_stats.py            # последние дни (по умолчанию)
    python3 player_stats.py --days 30  # сколько дней назад смотреть
    python3 player_stats.py --json     # сырой JSON-ответ воркера

Результаты пишутся в ../stats_results/ (player_stats.json + player_stats.md).
"""

import argparse
import datetime as dt
import json
import os
import urllib.request

API = "https://ru-catfishing-stats.ru-catfishing.workers.dev"
# Якорь нумерации дней: day0 = 2026-06-04 (см. app/src/lib/days/index.js).
ANCHOR = dt.date(2026, 6, 4)
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "stats_results")

RU_WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def date_for_day(day_idx: int) -> dt.date:
    return ANCHOR + dt.timedelta(days=day_idx)


def fetch_agg(day_indexes):
    q = ",".join(str(d) for d in day_indexes)
    url = f"{API}/agg?days={q}"
    req = urllib.request.Request(url, headers={"User-Agent": "player-stats/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=14,
                    help="сколько дней назад запрашивать (по умолчанию 14)")
    ap.add_argument("--json", action="store_true",
                    help="напечатать сырой JSON-ответ и выйти")
    args = ap.parse_args()

    # avgByDay в ответе глобальный (по всем дням), но days=... нужен, чтобы
    # охватить отрицательные/будущие индексы; запрашиваем щедрый диапазон.
    span = list(range(-10, args.days + 1))
    agg = fetch_agg(span)

    if args.json:
        print(json.dumps(agg, ensure_ascii=False, indent=2))
        return

    if not agg.get("ok"):
        raise SystemExit(f"Воркер вернул ошибку: {agg}")

    avg_by_day = agg.get("avgByDay", {})
    # Ключи приходят строками; приводим к int и сортируем по дате.
    rows = []
    for k, v in avg_by_day.items():
        day_idx = int(k)
        d = date_for_day(day_idx)
        rows.append({
            "day": day_idx,
            "date": d.isoformat(),
            "weekday": RU_WEEKDAYS[d.weekday()],
            "players": int(v.get("n", 0)),
            "avg_score": round(float(v.get("avg", 0)), 2),
        })
    rows.sort(key=lambda r: r["day"])

    total_plays = agg.get("totalPlays", sum(r["players"] for r in rows))
    all_time_avg = agg.get("allTimeAvg")
    total_opens = agg.get("totalOpens", 0)

    # ---- консольный вывод ----
    print("ru-catfishing — игроки по дням")
    print(f"(снято {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} локально)\n")
    print(f"{'день':>5}  {'дата':<10} {'дн':<3} {'игроков':>8} {'ср.балл':>8}")
    print("-" * 42)
    for r in rows:
        print(f"{r['day']:>5}  {r['date']:<10} {r['weekday']:<3} "
              f"{r['players']:>8} {r['avg_score']:>8.2f}")
    print("-" * 42)
    print(f"{'итого партий (день×игрок):':>30} {total_plays:>6}")
    if all_time_avg is not None:
        print(f"{'средний балл за всё время:':>30} {all_time_avg:>6.2f} / 10")
    print(f"{'открытий статей в Вики:':>30} {total_opens:>6}")

    # ---- сохранение результатов ----
    os.makedirs(RESULTS_DIR, exist_ok=True)
    snapshot = {
        "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
        "anchor_day0": ANCHOR.isoformat(),
        "per_day": rows,
        "total_plays": total_plays,
        "all_time_avg": all_time_avg,
        "total_opens": total_opens,
    }
    json_path = os.path.join(RESULTS_DIR, "player_stats.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    md_path = os.path.join(RESULTS_DIR, "player_stats.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# ru-catfishing — статистика игроков\n\n")
        f.write(f"Снято: **{snapshot['fetched_at']}** (локальное время)\n\n")
        f.write("Источник: глобальный стат-воркер `/agg` "
                "(Cloudflare Worker + D1).\n\n")
        f.write("`игроков` = число людей, завершивших этот день "
                "(одна запись на clientId+день).\n\n")
        f.write("| день | дата | дн | игроков | ср. балл |\n")
        f.write("|---:|---|---|---:|---:|\n")
        for r in rows:
            f.write(f"| {r['day']} | {r['date']} | {r['weekday']} | "
                    f"{r['players']} | {r['avg_score']:.2f} |\n")
        f.write(f"\n**Итого партий (день×игрок):** {total_plays}  \n")
        if all_time_avg is not None:
            f.write(f"**Средний балл за всё время:** {all_time_avg:.2f} / 10  \n")
        f.write(f"**Открытий статей в Вики:** {total_opens}  \n")

    print(f"\nСохранено:\n  {os.path.normpath(json_path)}\n  {os.path.normpath(md_path)}")


if __name__ == "__main__":
    main()
