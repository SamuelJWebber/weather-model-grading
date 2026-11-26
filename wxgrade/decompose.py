"""Error decomposition and inter-model error correlation (offline from
cached inputs).

Questions, asked of the cached Single Runs payloads and the station
actuals (no model reruns):
1. Do models only lose to persistence on QUIET days? Split each series'
   paired MAE into change days (|depth delta vs prior present day| >=
   threshold) vs quiet days, at several thresholds.
2. Do the models make the SAME errors? Pearson correlation of per-day
   signed errors between model pairs (and each model vs persistence) on
   common dates. Correlation alone does not establish ensemble benefit or harm.

Small-n descriptive analysis, not a skill claim; n is reported per cell.
"""

from __future__ import annotations

from datetime import date, timedelta


def classify_days(actual: dict[str, float], threshold_m: float,
                  tolerance_m: float = 0.0) -> dict[str, str]:
    """'change' if |actual[d] - actual[d-1]| >= threshold (both present),
    else 'quiet'. Days without a prior present day are omitted."""
    from datetime import date, timedelta
    out: dict[str, str] = {}
    for d in sorted(actual):
        prev = (date.fromisoformat(d) - timedelta(days=1)).isoformat()
        if prev in actual:
            out[d] = ("change" if abs(actual[d] - actual[prev])
                      >= threshold_m - tolerance_m else "quiet")
    return out


def delta_persistence_baseline(actual: dict[str, float]) -> dict[str, float]:
    """W3: persist the last observed day-over-day change (linear
    extrapolation): pred[d] = actual[d-1] + (actual[d-1] - actual[d-2]).
    Only where both prior days are present."""
    days = sorted(actual)
    out: dict[str, float] = {}
    for d in days:
        d1 = (date.fromisoformat(d) - timedelta(days=1)).isoformat()
        d2 = (date.fromisoformat(d) - timedelta(days=2)).isoformat()
        if d1 in actual and d2 in actual:
            out[d] = actual[d1] + (actual[d1] - actual[d2])
    return out


def model_delta_persistence(actual, pred):
    """Yesterday's observed depth plus the model's day-to-day depth change.
    Uses consecutive valid-day forecasts, not a future actual.
    """
    out = {}
    for d in pred:
        prev = (date.fromisoformat(d) - timedelta(days=1)).isoformat()
        if prev in actual and prev in pred:
            out[d] = actual[prev] + pred[d] - pred[prev]
    return out


def classify_days_exante(pred: dict[str, float], actual: dict[str, float],
                         threshold_m: float) -> dict[str, str]:
    """W2 supplement: ex-ante stratification, using only information
    available BEFORE the day: 'change' if |pred[d] - actual[d-1]| >=
    threshold (model-predicted move vs the last observed depth), else
    'quiet'. Unclassifiable days (missing prior actual or prediction)
    are omitted."""
    out: dict[str, str] = {}
    for d in sorted(pred):
        prev = (date.fromisoformat(d) - timedelta(days=1)).isoformat()
        if prev in actual:
            out[d] = ("change" if abs(pred[d] - actual[prev])
                      >= threshold_m else "quiet")
    return out


INCH_M = 0.0254


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


def supplementary_cells(actual: dict[str, float],
                        series: dict[str, dict[str, float]],
                        ref_model: str = "gfs_seamless") -> dict:
    """W2 supplements, SEPARATELY LABELED - the frozen 1/2/3cm cells above
    are unchanged. Two additions: (1) inch-denominated realized-change
    strata at 1/2/3in with MAEs reported in inches; (2) ex-ante strata
    (forecast-predicted change vs the prior observed depth), which is a
    usable selector, unlike the realized-change strata (retrospective
    diagnostics, and persistence's stratum split is near-tautological
    since its error is |delta actual| by construction)."""
    supp: dict = {"inch_thresholds": {}, "ex_ante_ref_model": ref_model,
                  "ex_ante": {}}
    common = set(actual)
    for pred in series.values():
        common &= set(pred)
    for inches in (1, 2, 3):
        thr = inches * INCH_M
        kinds = classify_days(actual, thr, tolerance_m=1e-9)
        days_by_kind = {"change": [d for d, k in kinds.items()
                                   if k == "change" and d in common],
                        "quiet": [d for d, k in kinds.items()
                                  if k == "quiet" and d in common]}
        cell = {kind: {name: (None if sc is None or sc["mae"] is None else
                              {"n": sc["n"],
                               "mae_in": round(sc["mae"] / INCH_M, 2)})
                       for name in series
                       for sc in [subset_scores(series[name], actual, ds)]}
                for kind, ds in days_by_kind.items()}
        cell["change_day_count"] = len(days_by_kind["change"])
        supp["inch_thresholds"][f"{inches}in"] = cell
    for inches in (1, 2, 3):
        thr = inches * INCH_M
        ref = series.get(ref_model, {})
        kinds = classify_days_exante(ref, actual, thr)
        days_by_kind = {"predicted_change": [d for d, k in kinds.items()
                                             if k == "change" and d in common],
                        "predicted_quiet": [d for d, k in kinds.items()
                                            if k == "quiet" and d in common]}
        supp["ex_ante"][f"{inches}in"] = {
            kind: {name: (None if sc is None or sc["mae"] is None else
                          {"n": sc["n"],
                           "mae_in": round(sc["mae"] / INCH_M, 2)})
                   for name in series
                   for sc in [subset_scores(series[name], actual, ds)]}
            for kind, ds in days_by_kind.items()}
    return supp


def subset_scores(pred: dict[str, float], actual: dict[str, float],
                  days: list[str]) -> dict | None:
    errs = [pred[d] - actual[d] for d in days
            if d in pred and d in actual]
    if not errs:
        return None
    n = len(errs)
    mae = sum(abs(e) for e in errs) / n
    rmse = (sum(e * e for e in errs) / n) ** 0.5
    return {"n": n, "mae": mae, "rmse": rmse, "bias": sum(errs) / n}


def overall_paired_scores(actual: dict[str, float],
                          series: dict[str, dict[str, float]]) -> dict:
    """W1: score EVERY series (models, ensemble, baselines) on the dates
    where ALL series and the actual are present - the overall paired
    comparison the audit found missing for the ensemble."""
    names = sorted(series)
    common = set(actual)
    for name in names:
        common &= set(series[name])
    days = sorted(common)
    return {name: subset_scores(series[name], actual, days)
            for name in names}


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


DEFAULT_WINDOWS = {"vail": ("2026-10-24", "2026-11-24"),
                   "breckenridge": ("2026-10-24", "2026-11-24"),
                   "park_city": ("2026-10-24", "2026-11-24"),
                   "palisades": ("2026-10-24", "2026-11-24"),
                   "stowe": ("2026-10-26", "2026-11-24")}


def run_decomposition_live(output_dir: str = "results",
                           windows: dict | None = None,
                           out_name: str = "decomposition_2026-11-26.json",
                           allow_fetch: bool = True
                           ) -> dict:
    """MANUAL ONLY: decomposition + error correlations for the graded
    stations, from cached Single Runs payloads (fetching only what's
    missing) plus one actuals pull per station. Short-lead series only
    (8h SNOTEL / 21h COOP) - the freshest forecast each day.

    FORWARD-TEST USE: pass `windows` (e.g. a storm window) and a new
    `out_name`; the thresholds (1/2/3cm) and change-day definition are
    frozen (README 2026-11-26) and are NOT retuned to future results."""
    import json
    from datetime import date, datetime, timedelta, timezone
    from pathlib import Path
    from .actuals import load_actuals
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
    windows = windows or DEFAULT_WINDOWS
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
        fetch_start = (date.fromisoformat(start)
                       - timedelta(days=1)).isoformat()
        if resort == "stowe":
            actual, actuals_meta = load_actuals(
                "coop", st["station"], fetch_start, end,
                lambda: fetch_snowd_daily(st["station"], st["network"],
                                          fetch_start, end),
                output_dir=output_dir, allow_fetch=allow_fetch)
            valid_h, lead_h = SAMPLE_UTC_HOUR, 21
            lat, lon = st["lat"], st["lon"]
        else:
            actual, actuals_meta = load_actuals(
                "snotel", st["triplet"], fetch_start, end,
                lambda: fetch_snwd_daily(st["triplet"], fetch_start, end),
                output_dir=output_dir, allow_fetch=allow_fetch)
            valid_h, lead_h = STATION_MIDNIGHT_UTC_HOUR, 8
            loc = LOCATIONS[resort]
            lat, lon = loc["lat"], loc["lon"]
        series: dict[str, dict[str, float]] = {}
        for model in ("gfs_seamless", "icon_seamless", "ecmwf_ifs025"):
            pred: dict[str, float] = {}
            for d in dates:
                init = (date.fromisoformat(d)
                        - timedelta(hours=lead_h - valid_h)).isoformat()
                run = _singlerun_cached(lat, lon, model, init, cache,
                                        allow_fetch=allow_fetch)
                valid = f"{d}T{valid_h:02d}:00"
                if valid in run:
                    pred[d] = run[valid]
            series[model] = pred
        series["persistence_1d"] = persistence_baseline(actual, 1)
        delta = delta_persistence_baseline(actual)
        series["const_zero_depth"] = {d: 0.0 for d in dates}
        model_names = ("gfs_seamless", "icon_seamless", "ecmwf_ifs025")
        ensemble = {d: sum(series[m][d] for m in model_names) / 3
                    for d in dates if all(m in series and d in series[m]
                                          for m in model_names)}
        dec_series = dict(series)
        dec_series["ensemble_mean_3"] = ensemble
        out["resorts"][resort] = {
            "station": st.get("name", st.get("station")),
            "window": [start, end], "lead_h": lead_h,
            "actual_fetch_window": [fetch_start, end],
            "actuals_saved_to": actuals_meta.get("path"),
            "actual_days": len(actual),
            "overall_paired": overall_paired_scores(actual, dec_series),
            "delta_baseline_separate_common_dates": overall_paired_scores(
                actual, {**dec_series, "observed_linear_extrapolation": delta}),
            "model_delta_persistence_separate_common_dates": overall_paired_scores(
                actual, {**dec_series, **{
                    f"{m}_delta_persistence": model_delta_persistence(actual, series[m])
                    for m in model_names}}),
            "decomposition": decomposition(actual, dec_series),
            "supplementary_inch_exante": supplementary_cells(
                actual, dec_series),
            "error_correlations": error_correlations(
                actual, {k: series[k] for k in
                         model_names + ("persistence_1d",)
                         if k in series})}
    path = Path(output_dir) / out_name
    path.write_text(json.dumps(out, indent=2))
    return out
