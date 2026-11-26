"""Independent eastern mountain snow actuals: NWS COOP via Iowa State IEM.

SNOTEL covers the 11 western US states + Alaska ONLY - no stations in the
Northeast. The verified eastern alternative for Stowe is the NWS COOP
station MMNV1 "MT. MANSFIELD" (VT_COOP network, on the resort's own
mountain), served by the Iowa State IEM daily service (free, no key) -
the same IEM service family already used for METAR actuals.

Measured variable: snowd_in = snow DEPTH (inches), matching Open-Meteo's
snow_depth (meters). NOT snowfall; SNWD-style depth deltas are net of
settling/compaction, so snowfall grading stays on the archive basis.

Measurement contract (verified 2026-11-25, not assumed):
- The station is automated (SHEF/DCP sub-hourly feed), not a human 7am
  COOP observer. Its snow depth reports EXACTLY ONCE DAILY at 21:00 UTC
  (16:00 local EST): api/1/obhistory.json full=1 shows SDIRZZZ=7.0 at
  2026-11-15T21:00Z and SDIRZZZ=5.0 at 2026-11-18T21:00Z, and the
  daily.py snowd_in values for those dates are 7.0 and 5.0 respectively.
- Consequence: daily snowd_in[D] = snow depth at 21:00 UTC of date D,
  and forecast series must be sampled at that exact instant
  (timezone="UTC", hour 21). 21:00Z = 16:00 EST; the snow season sits
  entirely in standard time, so no DST ambiguity arises for grading.
  Summer behaviour (EDT) is unverified and irrelevant to snow grading.
- Coverage is PATCHY: the station files intermittently (e.g. 2026-11-20,
  11-22, 11-24 have no snowd value). Scores cover only days with values
  and report n explicitly; a thin n is a coverage fact, not a skill fact.

Elevation: stake at 1202m (IEM site metadata); Open-Meteo grid cell at
the station coordinate (44.5248, -72.8154) is 1199m (api.open-meteo.com
/v1/elevation, checked 2026-11-25) - a ~3m gap, so Stowe/Mt Mansfield is
a near-zero-elevation-gap head-to-head like Vail, unlike the other
SNOTEL diagnostics.

Source (verified live 2026-11-25):
https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py?network=VT_COOP&stations=MMNV1&sts=<start>T00:00Z&ets=<end>T00:00Z&var=snowd_in
Network access is MANUAL ONLY; tests run offline on a CSV fixture.
"""

from __future__ import annotations

import csv
import io
from typing import Mapping

from urllib.parse import urlencode
from urllib.request import Request, urlopen

USER_AGENT = "weather-model-grading/0.1.0 (personal research)"
DAILY_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py"
HIST_FORECAST_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
INCHES_TO_M = 0.0254

# Verified 2026-11-25 against IEM site metadata AND a live daily.py pull
# AND the obhistory SDIRZZZ 21:00Z check described in the module docstring.
COOP_STATIONS = {
    "stowe": {"station": "MMNV1", "network": "VT_COOP",
              "name": "MT. MANSFIELD", "lat": 44.5248, "lon": -72.8154,
              "elev_m": 1202,
              "note": "on the resort's mountain (Stowe covers Mt Mansfield's "
                      "flanks); grid cell at the station coordinate is "
                      "1199m (gap ~3m). ~12km west of the village "
                      "coordinate in grade.py:LOCATIONS."},
}
SAMPLE_UTC_HOUR = 21  # measurement contract: snowd_in[D] = depth at D 21:00 UTC


def parse_daily_csv(text: str) -> dict[str, float]:
    """Parse the IEM daily.py CSV. Returns {date: snowd_inches}; rows with
    missing/None snow depth are skipped (patchy coverage is explicit)."""
    out: dict[str, float] = {}
    for row in csv.DictReader(io.StringIO(text)):
        date = (row.get("day") or "").strip()
        raw = (row.get("snowd_in") or "").strip()
        if not date or raw in ("", "None", "M"):
            continue
        out[date] = float(raw)
    return out


def fetch_snowd_daily(station: str, network: str, start: str, end: str
                      ) -> dict[str, float]:
    """MANUAL ONLY: daily snow depth (meters) for a COOP station."""
    qs = urlencode({"network": network, "stations": station,
                    "sts": f"{start}T00:00Z", "ets": f"{end}T00:00Z",
                    "var": "snowd_in"})
    req = Request(f"{DAILY_URL}?{qs}", headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    return {d: v * INCHES_TO_M for d, v in parse_daily_csv(text).items()}


def fetch_histforecast_at_hour(lat: float, lon: float, model: str,
                               start: str, end: str) -> dict[str, float]:
    """MANUAL ONLY: daily snow depth (m) at 21:00 UTC from consecutive
    recent runs (Historical Forecast API; short mixed lead, "recent_run")."""
    import json as _json
    qs = urlencode({"latitude": lat, "longitude": lon, "start_date": start,
                    "end_date": end, "hourly": "snow_depth", "models": model,
                    "timezone": "UTC"})
    req = Request(f"{HIST_FORECAST_URL}?{qs}", headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        payload = _json.load(resp)
    hourly = payload.get("hourly", {})
    values = hourly.get("snow_depth", hourly.get(f"snow_depth_{model}", []))
    out: dict[str, float] = {}
    for t, v in zip(hourly.get("time", []), values):
        if v is not None and t.endswith(f"T{SAMPLE_UTC_HOUR:02d}:00"):
            out[t[:10]] = float(v)
    return out


def run_coop_leads_live(resort: str, past_days: int, output_dir,
                        leads_h: tuple = (21, 45),
                        station: dict | None = None) -> list:
    """MANUAL ONLY: controlled-lead snow-depth grading vs COOP actuals.

    Valid instant = 21:00 UTC (the station's daily report instant); each
    (model, lead) series uses only archived Single Runs API runs
    initialised at 00:00 UTC exactly lead hours before the valid instant
    (21h = same-day run, 45h = prior-day run). Per-date init/valid
    provenance recorded per row, as in the SNOTEL leads route.
    """
    import json
    from datetime import date, datetime, timedelta, timezone
    from pathlib import Path
    from .grade import score_series, persistence_baseline
    from .snotel import _singlerun_cached, storm_dates

    st = station or COOP_STATIONS[resort]
    end = date.today() - timedelta(days=1)
    dates = [(end - timedelta(days=k)).isoformat()
             for k in range(past_days - 1, -1, -1)]
    actual = fetch_snowd_daily(st["station"], st["network"],
                               dates[0], dates[-1])
    storms = storm_dates(actual)
    rows = []
    for model in ("gfs_seamless", "icon_seamless", "ecmwf_ifs025"):
        runs: dict[str, dict[str, float]] = {}
        for lead in leads_h:
            pred: dict[str, float] = {}
            provenance: dict[str, dict[str, str]] = {}
            for d in dates:
                init = (date.fromisoformat(d)
                        - timedelta(hours=lead - SAMPLE_UTC_HOUR)
                        ).isoformat()
                if init not in runs:
                    runs[init] = fetch_singlerun_hourly(
                        st["lat"], st["lon"], model, init)
                valid = f"{d}T{SAMPLE_UTC_HOUR:02d}:00"
                if valid in runs[init]:
                    pred[d] = runs[init][valid]
                    provenance[d] = {"init": f"{init}T00:00Z",
                                     "valid": valid + "Z"}
            row = {"model": model, "lead": f"lead_{lead}h",
                   **score_series(pred, actual)}
            row["storm_subset"] = {
                "threshold_m": 0.05,
                "definition": "dates where the daily depth rose >= "
                              "threshold vs prior present day (undercounts "
                              "events: depth deltas are net of "
                              "settling/compaction)",
                **score_series({d: v for d, v in pred.items() if d in storms},
                               {d: v for d, v in actual.items() if d in storms})}
            row["provenance"] = provenance
            rows.append(row)
    base = persistence_baseline(actual, 1)
    base_row = {"model": "persistence_1d", "lead": "baseline",
                **score_series(base, actual)}
    base_row["storm_subset"] = {
        "threshold_m": 0.05,
        "definition": "dates where the daily depth rose >= threshold vs "
                      "prior present day (undercounts events: depth deltas "
                      "are net of settling/compaction)",
        **score_series({d: v for d, v in base.items() if d in storms},
                       {d: v for d, v in actual.items() if d in storms})}
    rows.append(base_row)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"grading_{resort}_snow-depth-coop-leads_{end.isoformat()}.json"
    out_path.write_text(json.dumps({
        "resort": resort, "station": st, "variable": "snow_depth",
        "basis": "forecast: model grid-cell snow_depth at 21:00 UTC from "
                 "archived Single Runs API runs initialised exactly lead "
                 "hours earlier (00:00 UTC inits; per-date init/valid "
                 "provenance recorded per row); actual: NWS COOP daily "
                 "snowd_in via IEM, the same instant (verified 2026-11-25: "
                 "snow depth reports once daily at 21:00 UTC). Same "
                 "variable/instant/units; grid cell (1199m) vs stake "
                 "(1202m) elevation gap ~3m.",
        "coverage": "COOP station files intermittently; scores cover only "
                    "days with a snowd value and n is reported per row.",
        "archive_limits": "Single Runs API archive reach measured "
                          "2026-11-25 (results/singleruns_availability_"
                          "2026-11-25.json): runs served from 2026-04-02 "
                          "onward for gfs/icon/ecmwf.",
        "actual_window": [dates[0], dates[-1]],
        "pull_utc": datetime.now(timezone.utc).isoformat(),
        "rows": rows}, indent=2))
    return rows


def paired_leads_check(resort: str = "stowe",
                       leads_h: tuple[int, ...] = (21, 45),
                       compare_to: str | None =
                       "results/grading_{r}_snow-depth-coop-leads_"
                       "2026-11-24.json",
                       output_dir: str = "results",
                       allow_fetch: bool = True) -> dict:
    """Paired same-day comparison: every series scored on the dates where
    ALL series (models at both leads AND the persistence baseline) AND the
    actual have values. The preserved leads artifact reports each series on
    its own available dates (n=26 models vs n=23 persistence), which is not
    a paired comparison; this check is.

    The window and inputs are re-derived for the preserved artifact's exact
    actual_window (not re-anchored to "yesterday"), and each series'
    unrestricted scores are recomputed and compared to the artifact: they
    must match exactly, proving the paired subset is drawn from the same
    underlying data. The original artifact is not modified.
    """
    import json
    from datetime import date, timedelta
    from pathlib import Path
    from .grade import score_series, persistence_baseline
    from .snotel import _singlerun_cached

    st = COOP_STATIONS[resort]
    ref_path = Path(compare_to.format(r=resort)) if compare_to else None
    ref = json.loads(ref_path.read_text()) if ref_path else None
    if ref:
        start, end = ref["actual_window"]
    else:
        end = (date.today() - timedelta(days=1)).isoformat()
        start = (date.fromisoformat(end) - timedelta(days=29)).isoformat()
    dates = [(date.fromisoformat(start) + timedelta(days=k)).isoformat()
             for k in range((date.fromisoformat(end)
                             - date.fromisoformat(start)).days + 1)]
    from .actuals import load_actuals
    actual, actuals_meta = load_actuals(
        "coop", st["station"], start, end,
        lambda: fetch_snowd_daily(st["station"], st["network"], start, end),
        output_dir=output_dir, allow_fetch=allow_fetch)

    series: dict[str, dict[str, float]] = {}
    runs: dict[tuple[str, str], dict[str, float]] = {}
    for model in ("gfs_seamless", "icon_seamless", "ecmwf_ifs025"):
        for lead in leads_h:
            pred: dict[str, float] = {}
            for d in dates:
                init = (date.fromisoformat(d)
                        - timedelta(hours=lead - SAMPLE_UTC_HOUR)
                        ).isoformat()
                if (model, init) not in runs:
                    runs[(model, init)] = _singlerun_cached(
                        st["lat"], st["lon"], model, init,
                        Path(output_dir) / "raw" / "singleruns",
                        allow_fetch=allow_fetch)
                valid = f"{d}T{SAMPLE_UTC_HOUR:02d}:00"
                if valid in runs[(model, init)]:
                    pred[d] = runs[(model, init)][valid]
            series[f"{model} lead_{lead}h"] = pred
    series["persistence_1d baseline"] = persistence_baseline(actual, 1)
    for lead in leads_h:  # W1: ensemble of the 3 models at each lead
        series[f"ensemble_mean_3 lead_{lead}h"] = {
            d: sum(series[f"{m} lead_{lead}h"][d]
                   for m in ("gfs_seamless", "icon_seamless",
                             "ecmwf_ifs025")) / 3
            for d in dates
            if all(d in series[f"{m} lead_{lead}h"]
                   for m in ("gfs_seamless", "icon_seamless",
                             "ecmwf_ifs025"))}

    # 1) identity check: unrestricted scores must reproduce the artifact
    identity = {}
    if ref:
        ref_rows = {(r["model"], r["lead"]): r for r in ref["rows"]}
        for name, pred in series.items():
            if name.startswith("ensemble_mean_3"):
                continue  # no row in the preserved artifact to verify
            model, lead = name.rsplit(" ", 1)
            got = score_series(pred, actual)
            want = ref_rows.get((model, lead))
            identity[name] = {
                "recomputed": got,
                "artifact": {k: want[k] for k in ("n", "mae", "rmse", "bias")}
                if want else None,
                "matches": bool(want) and all(
                    got[k] == want[k] for k in ("n", "mae", "rmse", "bias"))}

    # 2) paired scores on the common date intersection
    common = set(actual)
    for pred in series.values():
        common &= set(pred)
    common_dates = sorted(common)
    paired = {}
    for name, pred in series.items():
        errs = [pred[d] - actual[d] for d in common_dates]
        n = len(errs)
        paired[name] = {
            "n": n,
            "mae": round(sum(abs(e) for e in errs) / n, 4),
            "rmse": round((sum(e * e for e in errs) / n) ** 0.5, 4),
            "bias": round(sum(errs) / n, 4)}

    from .decompose import (delta_persistence_baseline, model_delta_persistence,
                            subset_scores)
    from .actuals import load_actuals
    history, history_meta = actual, actuals_meta
    delta = delta_persistence_baseline(history)
    supplements = {
        "constant_zero_depth": subset_scores(
            {d: 0.0 for d in common_dates}, actual, common_dates),
        "observed_linear_extrapolation": subset_scores(delta, actual, common_dates),
        "model_delta_persistence": {
            name: subset_scores(model_delta_persistence(history, pred), actual, common_dates)
            for name, pred in series.items() if "lead_" in name},
        "delta_missing_common_dates": sorted(set(common_dates) - set(delta)),
        "history_actuals": history_meta}
    out = {
        "check": "paired same-day comparison on the intersection of dates "
                 "where every model/lead, persistence AND the actual all "
                 "have values; fixes the unpaired n=26-vs-n=23 contrast in "
                 "the preserved artifact (which is not modified)",
        "resort": resort, "station": st["station"],
        "actual_window": [start, end],
        "actuals_provenance": actuals_meta,
        "common_dates": common_dates,
        "identity_check_vs_preserved_artifact": identity,
        "paired_scores": paired,
        "supplementary_baselines": supplements,
        "pull_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat()}
    out_path = (Path(output_dir)
                / f"grading_{resort}_snow-depth-coop-leads-paired_{end}.json")
    out_path.write_text(json.dumps(out, indent=2))
    return out
