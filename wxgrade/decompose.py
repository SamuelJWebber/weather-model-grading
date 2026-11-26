"""Error decomposition and inter-model error correlation (offline from
cached inputs).

Questions, asked of the cached Single Runs payloads and the station
actuals (no model reruns):
1. Do models only lose to persistence on QUIET days? Split each series'
   paired MAE into change days (|depth delta vs prior present day| >=
   threshold) vs quiet days, at several thresholds.
2. Do the models make the SAME errors? Pearson correlation of per-day
   signed errors between model pairs (and each model vs persistence) on
   common dates. High correlations mean an ensemble adds little.

Small-n descriptive analysis, not a skill claim; n is reported per cell.
"""

from __future__ import annotations


def classify_days(actual: dict[str, float], threshold_m: float
                  ) -> dict[str, str]:
    """'change' if |actual[d] - actual[d-1]| >= threshold (both present),
    else 'quiet'. Days without a prior present day are omitted."""
    from datetime import date, timedelta
    out: dict[str, str] = {}
    for d in sorted(actual):
        prev = (date.fromisoformat(d) - timedelta(days=1)).isoformat()
        if prev in actual:
            out[d] = ("change" if abs(actual[d] - actual[prev])
                      >= threshold_m else "quiet")
    return out


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return round(sum((x - mx) * (y - my)
                     for x, y in zip(xs, ys)) / (sxx * syy) ** 0.5, 3)


def subset_mae(pred: dict[str, float], actual: dict[str, float],
               days: list[str]) -> dict:
    errs = [abs(pred[d] - actual[d]) for d in days
            if d in pred and d in actual]
    if not errs:
        return {"n": 0, "mae": None}
    return {"n": len(errs), "mae": round(sum(errs) / len(errs), 4)}


def decomposition(actual: dict[str, float],
                  series: dict[str, dict[str, float]],
                  thresholds_m=(0.01, 0.02, 0.03)) -> dict:
    """Paired MAE per series on change vs quiet days, per threshold."""
    out = {}
    for thr in thresholds_m:
        kinds = classify_days(actual, thr)
        cell = {}
        for kind in ("change", "quiet"):
            days = [d for d, k in kinds.items() if k == kind]
            # paired: intersect across all series
            common = set(days)
            for pred in series.values():
                common &= set(pred)
            days = sorted(common)
            cell[kind] = {name: subset_mae(pred, actual, days)
                          for name, pred in series.items()}
            cell[kind]["paired_days"] = len(days)
        out[f"threshold_{thr}"] = cell
    return out


def error_correlations(actual: dict[str, float],
                       series: dict[str, dict[str, float]]) -> dict:
    """Pearson r of signed per-day errors between series, on dates common
    to BOTH series and the actual (per pair)."""
    names = sorted(series)
    out = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            days = sorted(set(series[a]) & set(series[b]) & set(actual))
            xs = [series[a][d] - actual[d] for d in days]
            ys = [series[b][d] - actual[d] for d in days]
            out[f"{a} vs {b}"] = {"n": len(days), "pearson": pearson(xs, ys)}
    return out


def run_decomposition_live(output_dir: str = "results") -> dict:
    """MANUAL ONLY: decomposition + error correlations for all 5 graded
    stations, from cached Single Runs payloads (fetching only what's
    missing) plus one actuals pull per station. Short-lead series only
    (8h SNOTEL / 21h COOP) - the freshest forecast each day."""
    import json
    from datetime import date, datetime, timedelta, timezone
    from pathlib import Path
    from .coop import COOP_STATIONS, SAMPLE_UTC_HOUR, fetch_snowd_daily
    from .grade import LOCATIONS, persistence_baseline
    from .snotel import (ELEVATION_MATCHED_STATIONS, RESORT_STATIONS,
                         STATION_MIDNIGHT_UTC_HOUR, _singlerun_cached,
                         fetch_snwd_daily)

    cache = Path(output_dir) / "raw" / "singleruns"
    resorts = {
        "vail": (RESORT_STATIONS["vail"], None),
        "breckenridge": (ELEVATION_MATCHED_STATIONS["breckenridge"], None),
        "park_city": (ELEVATION_MATCHED_STATIONS["park_city"], None),
        "palisades": (ELEVATION_MATCHED_STATIONS["palisades"], None),
        "stowe": (COOP_STATIONS["stowe"], None),
    }
    windows = {"vail": ("2026-10-24", "2026-11-24"),
               "breckenridge": ("2026-10-24", "2026-11-24"),
               "park_city": ("2026-10-24", "2026-11-24"),
               "palisades": ("2026-10-24", "2026-11-24"),
               "stowe": ("2026-10-26", "2026-11-24")}
    out: dict = {"basis": "short-lead (8h SNOTEL / 21h COOP) grid-cell "
                          "snow_depth at the station's valid instant vs "
                          "station actual; models from cached Single Runs "
                          "payloads (results/raw/singleruns/), actuals "
                          "pulled once per station; change day = |depth "
                          "delta vs prior present day| >= threshold; "
                          "descriptive, small n",
                 "pull_utc": datetime.now(timezone.utc).isoformat(),
                 "resorts": {}}
    for resort, (st, _) in resorts.items():
        start, end = windows[resort]
        dates = [(date.fromisoformat(start)
                  + timedelta(days=k)).isoformat()
                 for k in range((date.fromisoformat(end)
                                 - date.fromisoformat(start)).days + 1)]
        if resort == "stowe":
            actual = fetch_snowd_daily(st["station"], st["network"],
                                       start, end)
            valid_h, lead_h = SAMPLE_UTC_HOUR, 21
            lat, lon = st["lat"], st["lon"]
        else:
            actual = fetch_snwd_daily(st["triplet"], start, end)
            valid_h, lead_h = STATION_MIDNIGHT_UTC_HOUR, 8
            loc = LOCATIONS[resort]
            lat, lon = loc["lat"], loc["lon"]
        series: dict[str, dict[str, float]] = {}
        for model in ("gfs_seamless", "icon_seamless", "ecmwf_ifs025"):
            pred: dict[str, float] = {}
            for d in dates:
                init = (date.fromisoformat(d)
                        - timedelta(hours=lead_h - valid_h)).isoformat()
                run = _singlerun_cached(lat, lon, model, init, cache)
                valid = f"{d}T{valid_h:02d}:00"
                if valid in run:
                    pred[d] = run[valid]
            series[model] = pred
        series["persistence_1d"] = persistence_baseline(actual, 1)
        out["resorts"][resort] = {
            "station": st.get("name", st.get("station")),
            "window": [start, end], "lead_h": lead_h,
            "actual_days": len(actual),
            "decomposition": decomposition(actual, series),
            "error_correlations": error_correlations(actual, series)}
    path = Path(output_dir) / "decomposition_2026-11-26.json"
    path.write_text(json.dumps(out, indent=2))
    return out
