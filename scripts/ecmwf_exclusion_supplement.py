"""ECMWF-exclusion supplement (offline, non-mutating).

W3 resolution (results/ecmwf_zero_resolution_2026-11-26.json): ECMWF
snow_depth at the Copper (breckenridge) and Stowe grid cells is a suspect
series - exactly 0.0 in every cached/re-pulled run, including runs whose
own snowfall is nonzero. Root cause unresolved. Those cells' ECMWF depth
series are therefore excluded from grading interpretation.

This script recomputes, fully offline from cached raw Single Runs payloads
and saved actuals (network forbidden), for breckenridge and stowe:
  1. identity: every per-model paired score and the common dates reproduce
     the preserved paired artifacts exactly (proves same inputs);
  2. ensemble_mean_2 (gfs+icon only) per lead on the same common dates;
  3. the best single model excluding ecmwf;
  4. whether the stored conclusions (best-single at breck, ensemble rows at
     breck/stowe vs persistence) change.

Run from repo root: PYTHONPATH=. python3 scripts/ecmwf_exclusion_supplement.py
Writes results/ecmwf_exclusion_supplement_2026-11-26.json.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, '.')
from wxgrade import snotel, coop  # noqa: E402
from wxgrade.actuals import load_actuals  # noqa: E402
from wxgrade.grade import LOCATIONS, persistence_baseline, score_series  # noqa: E402

# network forbidden: cached raw runs and saved actuals only
snotel.fetch_singlerun_hourly = lambda *a, **k: (_ for _ in ()).throw(
    RuntimeError('network forbidden'))
snotel.fetch_snwd_daily = lambda *a, **k: (_ for _ in ()).throw(
    RuntimeError('network forbidden'))
coop.fetch_snowd_daily = lambda *a, **k: (_ for _ in ()).throw(
    RuntimeError('network forbidden'))

OUT_DIR = Path('results')
RUNS_DIR = OUT_DIR / 'raw' / 'singleruns'
MODELS = ("gfs_seamless", "icon_seamless", "ecmwf_ifs025")
KEEP = ("gfs_seamless", "icon_seamless")


def window_dates(start, end):
    return [(date.fromisoformat(start) + timedelta(days=k)).isoformat()
            for k in range((date.fromisoformat(end)
                            - date.fromisoformat(start)).days + 1)]


def build_series(dates, lat, lon, leads_h, valid_hour):
    runs = {}
    series = {}
    for model in MODELS:
        for lead in leads_h:
            pred = {}
            for d in dates:
                init = (date.fromisoformat(d)
                        - timedelta(hours=lead - valid_hour)).isoformat()
                if (model, init) not in runs:
                    runs[(model, init)] = snotel._singlerun_cached(
                        lat, lon, model, init, RUNS_DIR, allow_fetch=False)
                valid = f"{d}T{valid_hour:02d}:00"
                if valid in runs[(model, init)]:
                    pred[d] = runs[(model, init)][valid]
            series[f"{model} lead_{lead}h"] = pred
    return series


def paired_scores(series, actual, dates):
    """4-decimal scores over the intersection of ALL series + actual,
    matching the preserved paired artifacts' computation exactly."""
    all_series = dict(series)
    all_series["persistence_1d baseline"] = persistence_baseline(actual, 1)
    lead_tags = sorted({k.rsplit(' ', 1)[1] for k in series})
    for tag in lead_tags:
        all_series[f"ensemble_mean_2 {tag}"] = {
            d: (all_series[f"gfs_seamless {tag}"][d]
                + all_series[f"icon_seamless {tag}"][d]) / 2
            for d in dates
            if d in all_series[f"gfs_seamless {tag}"]
            and d in all_series[f"icon_seamless {tag}"]}
        all_series[f"ensemble_mean_3 {tag}"] = {
            d: sum(all_series[f"{m} {tag}"][d] for m in MODELS) / 3
            for d in dates
            if all(d in all_series[f"{m} {tag}"] for m in MODELS)}
    common = set(actual)
    for pred in all_series.values():
        common &= set(pred)
    common_dates = sorted(common)
    out = {}
    for name, pred in all_series.items():
        errs = [pred[d] - actual[d] for d in common_dates]
        n = len(errs)
        out[name] = {"n": n,
                     "mae": round(sum(abs(e) for e in errs) / n, 4),
                     "rmse": round((sum(e * e for e in errs) / n) ** 0.5, 4),
                     "bias": round(sum(errs) / n, 4),
                     "_dates": common_dates}
    return out


def main():
    report = {"check": "W3 follow-up: paired scores excluding suspect ECMWF "
                       "depth series at breckenridge(Copper) and stowe",
              "inputs": "cached raw Single Runs payloads + saved actuals, "
                        "network forbidden",
              "location_label_map": {
                  "breckenridge": "resort grid cell LOCATIONS['breckenridge'] "
                      "(39.48, -106.07, labeled 'Breckenridge, CO (Epic)'), "
                      "verified against elevation-matched SNOTEL station "
                      "415:CO:SNTL 'Copper Mountain' (8.8km away, 3200m vs "
                      "grid 3066m, gap +134m). 'Copper' labels in artifacts "
                      "and README refer to THIS station/grid pair, not the "
                      "Copper Mountain resort grid.",
                  "stowe": "resort grid = COOP station MMNV1 'MT. MANSFIELD' "
                      "own coordinates (44.5248, -72.8154); COOP route, "
                      "valid instant 21:00 UTC (SAMPLE_UTC_HOUR)."},
              "resorts": {}}

    # --- breckenridge (SNOTEL route, elevation-matched Copper station) ---
    ref = json.loads(Path(
        "results/grading_breckenridge_snow-depth-snotel-leads-paired-"
        "copper_mountain_2026-11-24.json").read_text())
    st = snotel.ELEVATION_MATCHED_STATIONS['breckenridge']
    loc = LOCATIONS['breckenridge']
    dates = window_dates(*ref["actual_window"])
    actual, _ = load_actuals("snotel", st["triplet"], *ref["actual_window"],
                             lambda: None, output_dir=OUT_DIR,
                             allow_fetch=False)
    series = build_series(dates, loc["lat"], loc["lon"], (8, 32),
                          snotel.STATION_MIDNIGHT_UTC_HOUR)
    report["resorts"]["breckenridge"] = _evaluate(
        ref, series, actual, dates, leads=(8, 32))

    # --- stowe (COOP route) ---
    ref = json.loads(Path(
        "results/grading_stowe_snow-depth-coop-leads-paired_"
        "2026-11-24.json").read_text())
    st = coop.COOP_STATIONS['stowe']
    dates = window_dates(*ref["actual_window"])
    actual, _ = load_actuals("coop", st["station"], *ref["actual_window"],
                             lambda: None, output_dir=OUT_DIR,
                             allow_fetch=False)
    series = build_series(dates, st["lat"], st["lon"], (21, 45),
                          coop.SAMPLE_UTC_HOUR)
    report["resorts"]["stowe"] = _evaluate(
        ref, series, actual, dates, leads=(21, 45))

    out_path = OUT_DIR / "ecmwf_exclusion_supplement_2026-11-26.json"
    out_path.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({r: v["conclusion"] for r, v in
                      report["resorts"].items()}, indent=2))
    print("wrote", out_path)


def _evaluate(ref, series, actual, dates, leads):
    scores = paired_scores(series, actual, dates)
    ref_scores = ref["paired_scores"]
    ref_dates = set(ref["common_dates"])
    # 1. identity: per-model + persistence scores must reproduce exactly
    identity = {}
    for name, want in ref_scores.items():
        got = scores.get(name)
        if got is None:
            identity[name] = {"matches": False, "reason": "not rebuilt"}
            continue
        identity[name] = {"matches": (
            got["n"] == want["n"] and got["mae"] == want["mae"]
            and got["rmse"] == want["rmse"] and got["bias"] == want["bias"]
            and set(got["_dates"]) == ref_dates)}
    ok = all(v["matches"] for v in identity.values())
    # 2/3. new ensemble and best single model excluding ecmwf
    slim = {k: {kk: vv for kk, vv in v.items() if kk != "_dates"}
            for k, v in scores.items()}
    best_excl = {}
    for lead in leads:
        cands = {m: slim[f"{m} lead_{lead}h"]["mae"] for m in KEEP}
        best_excl[f"lead_{lead}h"] = min(cands, key=cands.get)
    pers = slim["persistence_1d baseline"]
    e2 = {f"lead_{lead}h": slim[f"ensemble_mean_2 lead_{lead}h"]
          for lead in leads}
    e3 = {k: v for k, v in slim.items() if k.startswith("ensemble_mean_3")}
    conclusion = {
        "identity_check_vs_preserved_artifact": ok,
        "persistence": pers,
        "ensemble_mean_2_excl_ecmwf": e2,
        "stored_ensemble_mean_3_incl_ecmwf": e3,
        "best_single_excl_ecmwf": best_excl,
        "best_single_excl_ecmwf_beats_persistence": {
            lead: slim[f"{best_excl[lead]} {lead}"]["mae"] < pers["mae"]
            for lead in best_excl},
        "ensemble2_beats_persistence": {
            f"lead_{lead}h": slim[f"ensemble_mean_2 lead_{lead}h"]["mae"]
            < pers["mae"] for lead in leads},
        "ensemble3_beats_persistence": {
            k: v["mae"] < pers["mae"] for k, v in e3.items()},
    }
    if not ok:
        conclusion["WARNING"] = ("identity check FAILED - rebuilt inputs "
                                 "differ from preserved artifact; do not "
                                 "use these scores")
    return {"identity": identity, "scores_excl_ecmwf_plus_baselines": slim,
            "conclusion": conclusion}


if __name__ == "__main__":
    main()
