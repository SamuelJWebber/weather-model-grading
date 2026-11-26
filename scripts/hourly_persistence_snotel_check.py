"""Same-lead hourly persistence benchmark at the 3 remaining matched
SNOTEL stations (Copper Mountain/breck, Mill Creek Canyon/park_city,
Truckee #2/palisades). Companion to scripts/hourly_persistence_check.py
(Vail); Stowe is excluded because COOP MMNV1 reports daily only.

Per station: the hourly timestamp convention is verified empirically
against the saved daily series (candidate offsets 00:00 and 01:00,
>=95% match within 0.5in required), then gfs/icon at leads 8h/32h are
scored against persistence anchored lead-hours before the SAME valid
instant (08:00 UTC, the SNOTEL daily contract). RETROSPECTIVE symmetric
benchmark - anchors coincide with init and were NOT available at issue
time; not an operational selector and NOT an upper bound on operational
persistence skill (a more recent anchor does not guarantee smaller
realized error). A delayed-anchor sensitivity (anchors at init-3h,
init-24h, init-48h) is included as the feasible operational-direction
comparison - still archive-fed, so operational timeliness is assumed,
not established, for those delays.

Run from repo root:
  PYTHONPATH=. python3 scripts/hourly_persistence_snotel_check.py
Preserves raw hourly pulls under results/raw/actuals/ and writes
results/hourly_persistence_snotel_2026-11-26.json.
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
from wxgrade.grade import LOCATIONS, persistence_baseline  # noqa: E402

IN = 0.0254
OUT_DIR = Path('results')
RUNS_DIR = OUT_DIR / 'raw' / 'singleruns'
WINDOW = ("2026-10-24", "2026-11-24")
STATIONS = {
    "breckenridge": "415:CO:SNTL",
    "park_city": "1321:UT:SNTL",
    "palisades": "834:CA:SNTL",
}
MODELS = ("gfs_seamless", "icon_seamless")
LEADS = (8, 32)

snotel.fetch_singlerun_hourly = lambda *a, **k: (_ for _ in ()).throw(
    RuntimeError('network forbidden'))


def score(pred, actual, cd):
    errs = [pred[d] - actual[d] for d in cd]
    n = len(errs)
    if not n:
        return {"n": 0, "mae": None, "rmse": None, "bias": None}
    return {"n": n, "mae": round(sum(abs(e) for e in errs) / n, 4),
            "rmse": round((sum(e * e for e in errs) / n) ** 0.5, 4),
            "bias": round(sum(errs) / n, 4)}


def main():
    report = {"check": "same-lead hourly persistence vs model "
                       "forecasts, 3 matched SNOTEL stations; RETROSPECTIVE "
                       "symmetric benchmark (anchors unavailable at issue "
                       "time), NOT an upper bound on operational "
                       "persistence skill - see vail artifact",
              "window": list(WINDOW),
              "correction_2026-11-26_pm": (
                  "the first version of this check computed anchors with "
                  "date-minus-timedelta(hours), which drops sub-day "
                  "offsets (8h anchors landed ON the valid instant - MAE "
                  "exactly 0.0 was the tell; 32h anchors at valid-24h). "
                  "Anchors now use explicit UTC datetimes with each "
                  "station's verified CSV clock offset; all numbers in "
                  "this file are the corrected ones."),
              "retrospective_not_operational": (
                  "zero-lag anchors coincide with forecast init and were "
                  "not available at issue time; this is a retrospective "
                  "symmetric benchmark, NOT an upper bound on operational "
                  "persistence skill (a more recent anchor does not "
                  "guarantee smaller realized error). Delayed-anchor "
                  "sensitivities assume operational timeliness at the "
                  "stated delays; sampled SNOTEL hourly availability was "
                  "~1h on 2026-11-26 ~19:57 UTC (one sample, obslog), so "
                  "the 3h delay is plausible but not established."),
              "stations": {}}
    for resort, triplet in STATIONS.items():
        safe = triplet.replace(':', '-')
        src = f'/tmp/hourly_{safe}.csv'
        dst = OUT_DIR / 'raw' / 'actuals' / \
            f'snotel_{safe}_hourly_2026-10-22_2026-11-24.csv'
        shutil.copyfile(src, dst)
        sha = hashlib.sha256(dst.read_bytes()).hexdigest()
        hourly = {}
        for row in csv.reader(open(dst)):
            if not row or row[0].startswith('#') or row[0] == 'Date':
                continue
            if row[1].strip() in ('', 'M'):
                continue
            hourly[row[0]] = float(row[1]) * IN

        daily = json.loads((OUT_DIR / 'raw' / 'actuals'
                            / f'snotel_{safe}_2026-10-23_2026-11-24.json'
                            ).read_text())["values"]
        best_off, best_n = None, -1
        for off in ("00:00", "01:00"):
            m = sum(1 for d, v in daily.items()
                    if f"{d} {off}" in hourly
                    and abs(hourly[f"{d} {off}"] - v) < 0.013)
            if m > best_n:
                best_off, best_n = off, m
        verified = best_n >= 0.95 * len(daily)
        rec = {"triplet": triplet,
               "raw_hourly_csv": str(dst), "raw_hourly_csv_sha256": sha,
               "tz_contract": {"daily_matches_hourly_at": best_off,
                               "match": f"{best_n}/{len(daily)}",
                               "verified": verified}}
        if not verified:
            rec["skipped"] = ("timestamp convention could not be verified "
                              "against the saved daily series")
            report["stations"][resort] = rec
            continue

        dates = [(date.fromisoformat(WINDOW[0])
                  + timedelta(days=k)).isoformat()
                 for k in range((date.fromisoformat(WINDOW[1])
                                 - date.fromisoformat(WINDOW[0])).days + 1)]
        loc = LOCATIONS[resort]
        series = {}
        for model in MODELS:
            for lead in LEADS:
                pred = {}
                for d in dates:
                    init = (date.fromisoformat(d)
                            - timedelta(hours=lead - 8)).isoformat()
                    r = snotel._singlerun_cached(
                        loc["lat"], loc["lon"], model, init, RUNS_DIR,
                        allow_fetch=False)
                    valid = f"{d}T08:00"
                    if valid in r:
                        pred[d] = r[valid]
                series[f"{model} lead_{lead}h"] = pred
        actual = {d: hourly[f"{d} {best_off}"] for d in dates
                  if f"{d} {best_off}" in hourly}
        # anchor: valid minus lead hours, in the verified CSV convention.
        # best_off is the CSV clock hour of the 08:00 UTC valid instant.
        off_h = int(best_off[:2])
        from datetime import datetime

        def anchor_series(lead, delay_h):
            # anchor at init - delay_h; delay 0 = retrospective same-lead
            p = {}
            for d in dates:
                valid_utc = datetime.fromisoformat(d).replace(hour=8)
                anchor_utc = (valid_utc - timedelta(hours=lead)
                              - timedelta(hours=delay_h))
                # CSV clock offset implied by the verified daily match:
                # off_h=0 -> UTC-8, off_h=1 -> UTC-7
                csv_clock = anchor_utc - timedelta(hours=8 - off_h)
                key = csv_clock.strftime("%Y-%m-%d %H:00")
                if key in hourly:
                    p[d] = hourly[key]
            return p

        pers = {}
        for lead in LEADS:
            pers[f"hourly_persistence_{lead}h"] = anchor_series(lead, 0)
            for delay in (3, 24, 48):
                pers[f"hourly_persistence_{lead}h_delayed_{delay}h"] = \
                    anchor_series(lead, delay)
        dp = persistence_baseline(actual, 1)
        rec["scores"] = {}
        for lead in LEADS:
            names = [f"{m} lead_{lead}h" for m in MODELS]
            all_s = {n: series[n] for n in names}
            all_s[f"hourly_persistence_{lead}h"] = \
                pers[f"hourly_persistence_{lead}h"]
            common = set(actual)
            for p in all_s.values():
                common &= set(p)
            cd = sorted(common)
            block = {"common_dates": len(cd),
                     **{n: score(p, actual, cd) for n, p in all_s.items()}}
            cd2 = sorted(set(actual) & set(dp)
                         & set.intersection(*(set(series[n])
                                              for n in names)))
            block["daily_persistence_1d_same_dates"] = score(
                {d: dp[d] for d in cd2}, actual, cd2)
            block["hourly_persistence_beats_models"] = all(
                block[f"hourly_persistence_{lead}h"]["mae"]
                < block[f"{m} lead_{lead}h"]["mae"] for m in MODELS)
            # delayed anchors on their OWN maximal intersection with the
            # models (each delayed series reaches further back and would
            # otherwise shrink every series' common dates)
            sens = {}
            for delay in (3, 24, 48):
                pname = f"hourly_persistence_{lead}h_delayed_{delay}h"
                pd = pers[pname]
                cd3 = sorted(set(actual) & set(pd)
                             & set.intersection(*(set(series[n])
                                                  for n in names)))
                sens[f"delayed_{delay}h"] = {
                    "common_dates": len(cd3),
                    pname: score(pd, actual, cd3),
                    **{n: score(series[n], actual, cd3) for n in names},
                    "models_beat_delayed_persistence": {
                        m: score(series[f"{m} lead_{lead}h"], actual,
                                 cd3)["mae"] < score(pd, actual, cd3)["mae"]
                        for m in MODELS}}
            block["delayed_anchor_sensitivity"] = sens
            block["delayed_anchor_note"] = (
                "anchor at init minus delay. Directly sampled 2026-11-26 "
                "~19:57 UTC (results/raw/obslog/): SNOTEL hourly values "
                "available ~1h after the observation instant, so a "
                "3h-delayed anchor is PLAUSIBLE operationally for SNOTEL "
                "(not established - one sample); 24-48h delays are "
                "conservative by comparison. An earlier '>38h' lag claim "
                "was confounded by the requested window and is "
                "retracted.")
            rec["scores"][f"lead_{lead}h"] = block
        report["stations"][resort] = rec

    out_path = OUT_DIR / "hourly_persistence_snotel_2026-11-26.json"
    out_path.write_text(json.dumps(report, indent=1) + "\n")
    for r, rec in report["stations"].items():
        if "skipped" in rec:
            print(r, "SKIPPED:", rec["skipped"])
            continue
        for lead, b in rec["scores"].items():
            hp = b[f"hourly_persistence_{lead.split('_')[1]}".replace(
                'lead_', 'hourly_persistence_')]
            key = f"hourly_persistence_{lead[5:]}"
            print(r, lead, "n=", b["common_dates"],
                  "hourly-pers", b[key]["mae"],
                  "daily-pers", b["daily_persistence_1d_same_dates"]["mae"],
                  "gfs", b[f"gfs_seamless {lead}"]["mae"],
                  "icon", b[f"icon_seamless {lead}"]["mae"],
                  "hp_beats_models:", b["hourly_persistence_beats_models"])
    print("wrote", out_path)


if __name__ == "__main__":
    main()
