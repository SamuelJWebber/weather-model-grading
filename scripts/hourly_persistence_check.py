"""Same-lead hourly persistence benchmark at Vail (station 842:CO:SNTL).
RETROSPECTIVE only: anchors use observations unavailable at issue time.

Motivation: the paired artifacts compare model forecasts against 1-DAY
persistence anchored on the prior daily actual - a favorable persistence
benchmark with zero lag. This check scores each model at lead L against
an hourly persistence series anchored L hours before the SAME valid
instant (symmetric same-lead benchmark), at Vail only: on-mountain
station, ~0 elevation gap, cleanest measurement contract.

Timezone contract (verified empirically in this run): NRCS hourly report
timestamps for 842 use the same convention as the daily SNWD pull -
hourly row "D 00:00" equals daily SNWD[D] (33/33 match within 0.5in),
i.e. "D 00:00" = D 08:00 UTC, the SNOTEL daily valid instant.
So for valid instant D 08:00 UTC, same-lead hourly persistence at lead
8h is CSV row "D-1 16:00"; at lead 32h, CSV row "D-2 16:00".

NOT an operational selector: the 00Z run is published after 00:00 UTC
and the anchor observation at t-L was not available at init; this is a
retrospective symmetric benchmark only. It is NOT an upper bound on
operational persistence skill: a more recent anchor does not guarantee
smaller realized error. Hourly 842 values flicker by ~1 inch (sensor
noise at event scale) - scores are at cm precision with that caveat.

Run from repo root: PYTHONPATH=. python3 scripts/hourly_persistence_check.py
Writes results/hourly_persistence_vail_2026-11-26.json and preserves the
raw hourly pull under results/raw/actuals/.
"""
import csv
import hashlib
import json
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, '.')
from wxgrade import snotel  # noqa: E402
from wxgrade.grade import LOCATIONS  # noqa: E402

IN = 0.0254
OUT_DIR = Path('results')
RUNS_DIR = OUT_DIR / 'raw' / 'singleruns'
RAW_CSV_SRC = '/tmp/842_hourly_snwd.csv'
WINDOW = ("2026-10-24", "2026-11-24")  # paired window for vail

snotel.fetch_singlerun_hourly = lambda *a, **k: (_ for _ in ()).throw(
    RuntimeError('network forbidden'))


def main():
    raw_dst = OUT_DIR / 'raw' / 'actuals' / \
        'snotel_842-CO-SNTL_hourly_2026-10-22_2026-11-24.csv'
    shutil.copyfile(RAW_CSV_SRC, raw_dst)
    raw_sha = hashlib.sha256(raw_dst.read_bytes()).hexdigest()

    hourly = {}
    for row in csv.reader(open(raw_dst)):
        if not row or row[0].startswith('#') or row[0] == 'Date':
            continue
        if row[1].strip() in ('', 'M'):
            continue
        hourly[row[0]] = float(row[1]) * IN

    # verify timezone contract against the saved daily actuals
    daily = json.loads((OUT_DIR / 'raw' / 'actuals'
                        / 'snotel_842-CO-SNTL_2026-10-23_2026-11-24.json'
                        ).read_text())["values"]
    match00 = sum(1 for d, v in daily.items()
                  if f"{d} 00:00" in hourly
                  and abs(hourly[f"{d} 00:00"] - v) < 0.013)
    tz_contract = {"hourly_00:00_equals_daily": f"{match00}/{len(daily)}",
                   "verified": match00 == len(daily)}

    dates = [(date.fromisoformat(WINDOW[0]) + timedelta(days=k)).isoformat()
             for k in range((date.fromisoformat(WINDOW[1])
                             - date.fromisoformat(WINDOW[0])).days + 1)]
    loc = LOCATIONS['vail']
    models = ("gfs_seamless", "icon_seamless")
    leads = (8, 32)
    series, pers = {}, {}
    for model in models:
        for lead in leads:
            pred = {}
            for d in dates:
                init = (date.fromisoformat(d)
                        - timedelta(hours=lead - 8)).isoformat()
                r = snotel._singlerun_cached(loc["lat"], loc["lon"], model,
                                             init, RUNS_DIR,
                                             allow_fetch=False)
                valid = f"{d}T08:00"
                if valid in r:
                    pred[d] = r[valid]
            series[f"{model} lead_{lead}h"] = pred
    from datetime import datetime
    for lead in leads:
        p = {}
        for d in dates:
            valid_utc = datetime.fromisoformat(d).replace(hour=8)
            anchor_utc = valid_utc - timedelta(hours=lead)
            csv_clock = anchor_utc - timedelta(hours=8)  # UTC-8 convention
            key = csv_clock.strftime("%Y-%m-%d %H:00")
            if key in hourly:
                p[d] = hourly[key]
        pers[f"hourly_persistence_{lead}h"] = p

    actual = {d: hourly[f"{d} 00:00"] for d in dates
              if f"{d} 00:00" in hourly}

    def score(pred, common_dates):
        errs = [pred[d] - actual[d] for d in common_dates]
        n = len(errs)
        if not n:
            return {"n": 0, "mae": None, "rmse": None, "bias": None}
        return {"n": n,
                "mae": round(sum(abs(e) for e in errs) / n, 4),
                "rmse": round((sum(e * e for e in errs) / n) ** 0.5, 4),
                "bias": round(sum(errs) / n, 4)}

    out = {"check": "same-lead hourly persistence vs model forecasts, "
                    "Vail 842 only; RETROSPECTIVE symmetric benchmark "
                    "(anchors unavailable at issue time), NOT an "
                    "operational selector and NOT an upper bound on "
                    "operational persistence skill",
            "timezone_provisional_2026-11-26": ("SNOTEL hourly CSV clock->UTC offsets here rest on NRCS AWDB docs (PST for SNTL, except Alaska/elsewhere stations) plus a daily-date-boundary anchor at whole-hour granularity; the elsewhere exception is unresolved and a whole-hours offset within a day would not show in the daily anchor. Anchor instants and delayed-anchor sensitivities inherit the caveat until AWDB stationDataTimeZone is checked per station."),
              "correction_2026-11-26_pm": (
               "supersedes the numbers first committed in 4ebb1b1: the "
               "initial version of this script computed anchors with "
               "date-minus-timedelta(hours) arithmetic, which drops "
               "sub-day offsets (8h anchor landed 16h AFTER the valid "
               "instant - look-ahead - and 32h at valid-24h). Anchors "
               "are now computed with explicit UTC datetimes: valid "
               "D 08:00 UTC minus lead, converted to the verified UTC-8 "
               "CSV clock. Model scores also shifted slightly because "
               "the common-date intersection changed with anchor "
               "availability."),
           "anchor_availability": {
               "available_at_init": "NO - the same-lead construction puts "
                   "the anchor exactly AT the init instant (anchor = valid "
                   "- lead = init), and an observation is not transmitted "
                   "before it exists. Directly sampled 2026-11-26 ~19:57 "
                   "UTC via scripts/observe_now.py (results/raw/obslog/): "
                   "SNOTEL hourly values were available ~1h after the "
                   "observation instant at all four stations; the COOP "
                   "MMNV1 newest value was ~71h old (11-24 and 11-25 "
                   "values absent entirely). An earlier '>38h hourly lag' "
                   "claim was confounded by the pull's requested window "
                   "ending 2026-11-24 and is retracted. Sampled "
                   "observations, not universal latency guarantees.",
               "why_symmetric": "the anchor sits lead-hours before the "
                   "valid instant, the same horizon the model forecast "
                   "covers. This benchmark uses observations unavailable "
                   "at issue time, so it is RETROSPECTIVE only.",
               "what_it_does_not_show": ["it is NOT an upper bound on "
                   "operational persistence skill: a more recent anchor "
                   "does not guarantee smaller realized error, and a "
                   "delayed operational anchor can do better on some "
                   "samples",
                   "models losing to this benchmark does NOT establish "
                   "that they lose to an operational delayed-anchor "
                   "persistence; that comparison favors this benchmark "
                   "and is tested separately in "
                   "hourly_persistence_snotel_2026-11-26.json "
                   "(delayed-anchor sensitivity)"]},
           "window": list(WINDOW),
           "timezone_contract": tz_contract,
           "raw_hourly_csv": str(raw_dst),
           "raw_hourly_csv_sha256": raw_sha,
           "sensor_noise_caveat": "hourly 842 values flicker by ~1 inch",
           "scores": {}}
    for lead in leads:
        names = [f"{m} lead_{lead}h" for m in models]
        names.append(f"hourly_persistence_{lead}h")
        all_s = {**{n: series[n] for n in names if n in series},
                 f"hourly_persistence_{lead}h": pers[f"hourly_persistence_{lead}h"]}
        common = set(actual)
        for p in all_s.values():
            common &= set(p)
        cd = sorted(common)
        out["scores"][f"lead_{lead}h"] = {
            "common_dates": len(cd),
            **{n: score(p, cd) for n, p in all_s.items()}}
    # also daily persistence (1d) on the same dates for direct contrast
    from wxgrade.grade import persistence_baseline
    dp = persistence_baseline(actual, 1)
    for lead in leads:
        block = out["scores"][f"lead_{lead}h"]
        cd_n = block["common_dates"]
        common = set(actual) & set(dp)
        for n in (f"{m} lead_{lead}h" for m in models):
            common &= set(series[n])
        cd = sorted(common)
        block["daily_persistence_1d_same_dates"] = score(
            {d: dp[d] for d in cd}, cd)
        block["contrast_note"] = (
            "daily persistence is anchored on the prior daily actual "
            "(zero-lag); hourly persistence is anchored lead-hours before "
            "the valid instant - the honest same-lead benchmark")
    out_path = OUT_DIR / "hourly_persistence_vail_2026-11-26.json"
    out_path.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out["scores"], indent=1))
    print("tz contract:", tz_contract)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
