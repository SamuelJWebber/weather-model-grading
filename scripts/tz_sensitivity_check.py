#!/usr/bin/env python3
"""OFFLINE diagnostic: how sensitive are the existing same-lead hourly
persistence benchmark conclusions to the assumed SNOTEL hourly CSV
clock->UTC conversion?

Motivation: the +8h conversion is PROVISIONAL (NRCS AWDB docs: PST for
SNTL except "a few stations in Alaska and elsewhere"; the in-repo daily
anchor verifies only date-boundary assignment at whole-hour granularity).
This check does NOT resolve the true timezone. It re-scores the benchmark
under each assumed offset in a plausible diagnostic range and reports
whether the headline conclusions move.

Diagnostic range: UTC-6 .. UTC-10 (covers the US Pacific/Mountain/
Alaska standard+daylight candidates; the daily anchor already excludes
whole-DAY errors, so only within-day whole-hour shifts are in scope).

Method: identical data and scoring as
scripts/hourly_persistence_snotel_check.py (cached hourly actuals +
cached singleruns; no network). For each assumed offset h, BOTH the
actual selection (CSV clock = 08:00 UTC valid - h) and the persistence
anchor (valid - lead - 0/3h delay, minus h) shift consistently; model
predictions are offset-independent (init times fixed by the 08:00 UTC
daily contract). Scores are computed on COMMON PAIRED SUPPORT: the date
set present under EVERY offset in the range, per station/lead/delay, so
cross-offset comparisons are paired on identical dates.

Run from repo root: PYTHONPATH=. python3 scripts/tz_sensitivity_check.py
Writes results/tz_sensitivity_2026-11-26.json.
"""
import csv
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, '.')
from wxgrade import snotel  # noqa: E402
from wxgrade.grade import LOCATIONS  # noqa: E402

IN = 0.0254
OUT_DIR = Path('results')
RUNS_DIR = OUT_DIR / 'raw' / 'singleruns'
WINDOW = ("2026-10-24", "2026-11-24")
STATIONS = {
    "vail": "842:CO:SNTL",
    "breckenridge": "415:CO:SNTL",
    "park_city": "1321:UT:SNTL",
    "palisades": "834:CA:SNTL",
}
MODELS = ("gfs_seamless", "icon_seamless")
LEADS = (8, 32)
DELAYS = (0, 3)
OFFSETS = (6, 7, 8, 9, 10)  # diagnostic: CSV clock + h = UTC

snotel.fetch_singlerun_hourly = lambda *a, **k: (_ for _ in ()).throw(
    RuntimeError('network forbidden'))


def mae(errs):
    return round(sum(abs(e) for e in errs) / len(errs), 4) if errs else None


def main():
    dates = [(date.fromisoformat(WINDOW[0]) + timedelta(days=k)).isoformat()
             for k in range((date.fromisoformat(WINDOW[1])
                             - date.fromisoformat(WINDOW[0])).days + 1)]
    report = {
        "check": "OFFLINE diagnostic sensitivity of the same-lead hourly "
                 "persistence benchmark to the assumed SNOTEL hourly "
                 "timezone offset; does NOT resolve the true timezone",
        "window": list(WINDOW),
        "offsets_hours": list(OFFSETS),
        "common_support": "per station/lead/delay, only dates present "
                          "under every offset are scored",
        "limitations": [
            "diagnostic range is within-day whole hours only; the daily "
            "anchor already excludes whole-day errors",
            "a uniform per-station offset is assumed; a real station in "
            "a DST-observing local zone would have a MID-WINDOW offset "
            "shift, which no constant-offset variant represents",
            "common support shrinks n vs the headline artifact; MAEs "
            "here are not comparable to it, only across offsets",
            "archive-fed; says nothing about operational timeliness",
            "quiet support is degenerate for persistence: where actuals "
            "are constant (e.g., vail pre-storm, 5 distinct values over "
            "27 dates), persistence error is ~0 at ANY offset, so small "
            "MAE differences there carry little information"],
        "stations": {}}
    for resort, triplet in STATIONS.items():
        safe = triplet.replace(':', '-')
        path = OUT_DIR / 'raw' / 'actuals' / \
            f'snotel_{safe}_hourly_2026-10-22_2026-11-24.csv'
        hourly = {}
        for row in csv.reader(open(path)):
            if not row or row[0].startswith('#') or row[0] == 'Date':
                continue
            if row[1].strip() in ('', 'M'):
                continue
            hourly[row[0]] = float(row[1]) * IN

        # offset-independent model predictions, keyed by date/lead
        preds = {}
        for model in MODELS:
            for lead in LEADS:
                p = {}
                for d in dates:
                    init = (datetime.fromisoformat(d)
                            - timedelta(hours=lead - 8)).date().isoformat()
                    loc = LOCATIONS[resort]
                    r = snotel._singlerun_cached(
                        loc["lat"], loc["lon"],
                        model, init, RUNS_DIR, allow_fetch=False)
                    v = f"{d}T08:00"
                    if v in r:
                        p[d] = r[v]
                preds[(model, lead)] = p

        srec = {}
        for lead in LEADS:
            for delay in DELAYS:
                per_off = {}
                support = None
                for h in OFFSETS:
                    actual, anchor = {}, {}
                    for d in dates:
                        valid_utc = datetime.fromisoformat(d).replace(hour=8)
                        a_clock = valid_utc - timedelta(hours=h)
                        akey = a_clock.strftime("%Y-%m-%d %H:00")
                        if akey in hourly:
                            actual[d] = hourly[akey]
                        anch_utc = (valid_utc - timedelta(hours=lead)
                                    - timedelta(hours=delay))
                        k_clock = anch_utc - timedelta(hours=h)
                        kkey = k_clock.strftime("%Y-%m-%d %H:00")
                        if kkey in hourly:
                            anchor[d] = hourly[kkey]
                    common = [d for d in dates
                              if d in actual and d in anchor
                              and all(d in preds[(m, lead)] for m in MODELS)]
                    per_off[h] = (actual, anchor, common)
                    support = (set(common) if support is None
                               else support & set(common))
                common = sorted(support)
                row = {"n_common": len(common), "dates_common": common,
                       "by_offset": {}}
                for h in OFFSETS:
                    actual, anchor, _ = per_off[h]
                    cell = {"persistence_mae": mae(
                                [anchor[d] - actual[d] for d in common])}
                    for m in MODELS:
                        cell[f"{m}_mae"] = mae(
                            [preds[(m, lead)][d] - actual[d]
                             for d in common])
                    row["by_offset"][f"utc_minus_{h}"] = cell
                srec[f"lead_{lead}h_delay_{delay}h"] = row
        report["stations"][resort] = srec

    # verdict: does any headline conclusion move?
    conclusions = []
    for resort, srec in report["stations"].items():
        for key, row in srec.items():
            by = row["by_offset"]
            base = by["utc_minus_8"]
            base_winner = min(
                [(k[:-4], v) for k, v in base.items()], key=lambda kv: kv[1])[0]
            flips = []
            for h in OFFSETS:
                if h == 8:
                    continue
                w = min([(k[:-4], v) for k, v in by[f"utc_minus_{h}"].items()],
                        key=lambda kv: kv[1])[0]
                if w != base_winner:
                    flips.append((h, w))
            conclusions.append({"station": resort, "series": key,
                                "n_common": row["n_common"],
                                "winner_at_utc_minus_8": base_winner,
                                "winner_changes": flips})
    report["conclusion_stability"] = conclusions
    out = OUT_DIR / "tz_sensitivity_2026-11-26.json"
    out.write_text(json.dumps(report, indent=2))
    print("wrote", out)
    for c in conclusions:
        print(f"{c['station']:13s} {c['series']:22s} n={c['n_common']:2d} "
              f"winner@-8={c['winner_at_utc_minus_8']:16s} "
              f"changes={c['winner_changes']}")


if __name__ == "__main__":
    main()
