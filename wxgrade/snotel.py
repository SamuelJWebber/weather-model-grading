"""Independent mountain snow actuals from USDA NRCS SNOTEL stations.

SNOTEL is a physical snow-pillow network covering the 11 western US states
and Alaska ONLY - no stations in the Northeast (e.g. Stowe, VT has none;
the NWS COOP station on Mount Mansfield is the alternative there) and none
in Canada (Whistler) or Switzerland (Zermatt).

Measured variable: SNWD = snow DEPTH (inches, start-of-day). That matches
Open-Meteo's snow_depth forecast/archive variable (meters) - NOT snowfall.
Snowfall scoring against SNWD deltas would mix variables (settling and
compaction make depth deltas smaller than snowfall); this module therefore
only supplies snow depth actuals, and snowfall grading stays on the
archive basis with its event-thin caveat.

Measurement contract (verified 2026-11-25, not assumed):
- The daily CSV header literally reads "Snow Depth (in) Start of Day
  Values", and daily[D] == hourly[D 00:00] (checked at 842 for
  2026-11-24), so the daily value is the INSTANT at station midnight,
  not a day summary.
- NRCS reports station times in local STANDARD time at a fixed, per-
  station UTC offset with no DST, and the offset need not match the
  station's state zone. All four stations below report at UTC-8:
  opensnotel.com station records give utcOffsetMinutes=-480 for
  842/531 (CO), 814 (UT) and 784 (CA), corroborated empirically at
  ~08:00 UTC 2026-11-25 when every station's latest hourly stamp was
  23:00 the prior day (UTC-7 would have shown 00:00).
- Consequence: daily SNWD[D] = snow depth at 08:00 UTC of date D for
  these stations, and forecast series must be sampled at that exact
  instant (timezone="Etc/GMT+8", never the resort's IANA zone, which
  would shift one hour under DST and one hour vs these stations'
  reporting zone in winter).

Source (free, no key, verified live 2026-11-24):
report-generator CSV, e.g.
https://wcc.sc.egov.usda.gov/reportGenerator/view_csv/customSingleStationReport/daily/842:CO:SNTL|id=""|name/-7,0/SNWD::value
Network access is MANUAL ONLY; tests run offline on a CSV fixture.
"""

from __future__ import annotations

import csv
import io
from urllib.request import Request, urlopen

USER_AGENT = "weather-model-grading/0.1.0 (personal research)"
REPORT_URL = (
    "https://wcc.sc.egov.usda.gov/reportGenerator/view_csv/"
    "customSingleStationReport/daily/{triplet}%7Cid=%22%22%7Cname/{start},{end}/SNWD::value"
)
INCHES_TO_M = 0.0254

# Verified resort -> SNOTEL station map. ONLY stations checked against the
# NRCS active-station list / live endpoint belong here; extend cautiously.
RESORT_STATIONS = {
    # Each entry verified 2026-11-25 against the NRCS site page (name,
    # county, elevation) AND a live SNWD CSV pull. Distance to the resort
    # coordinate in grade.py:LOCATIONS is approximate straight-line.
    "vail": {"triplet": "842:CO:SNTL", "name": "Vail Mountain",
             "tz": "Etc/GMT+8", "note": "on-mountain, 2495m"},
    "breckenridge": {"triplet": "531:CO:SNTL", "name": "Hoosier Pass",
                     "tz": "Etc/GMT+8",
                     "note": "39.36,-106.06 at 11600ft, ~13km south; nearest by "
                             "distance is Copper Mountain (415) at ~9km/10500ft "
                             "but that pillow sits on a different resort's terrain"},
    "park_city": {"triplet": "814:UT:SNTL", "name": "Thaynes Canyon",
                  "tz": "Etc/GMT+8",
                  "note": "40.62,-111.53 at 9260ft, ~4km; on resort terrain"},
    "palisades": {"triplet": "784:CA:SNTL", "name": "Palisades Tahoe",
                  "tz": "Etc/GMT+8",
                  "note": "39.18,-120.27 at 8010ft, ~3km; named for the resort"},
    # NOT covered (verified 2026-11-24/25): stowe (no SNOTEL in VT; NWS COOP
    # on Mount Mansfield is the alternative, not integrated), whistler (BC),
    # zermatt (CH) - need national networks, unverified.
    # "tz" is the STATION REPORTING ZONE (fixed UTC offset, no DST) used to
    # sample the forecast at the same instant as the daily SNWD value; see
    # the measurement-contract note at the top of this module.
}


def parse_snwd_csv(text: str) -> dict[str, float]:
    """Parse the report-generator CSV (comment lines start with #).

    Returns {date: snow_depth_inches}; missing values are skipped.
    """
    lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
    rows = csv.DictReader(io.StringIO("\n".join(lines)))
    out: dict[str, float] = {}
    for row in rows:
        date = (row.get("Date") or "").strip()
        raw = (row.get("Snow Depth (in) Start of Day Values") or "").strip()
        if not date or raw in ("", "-"):
            continue
        out[date] = float(raw)
    return out


def fetch_snwd_daily(triplet: str, start: str, end: str) -> dict[str, float]:
    """MANUAL ONLY: daily start-of-day snow depth (meters) for a station."""
    url = REPORT_URL.format(triplet=triplet, start=start, end=end)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    return {d: v * INCHES_TO_M for d, v in parse_snwd_csv(text).items()}


HIST_FORECAST_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"

# Verified 2026-11-24: the Previous Runs API does NOT retain snow_depth
# (snow_depth_previous_dayN all-null for all four graded models). Verified
# 2026-11-25: the Single Runs API DOES serve snow_depth with non-null,
# run-resolved values for gfs_seamless / icon_seamless / ecmwf_ifs025
# (same valid instant, different runs -> different values), with the run's
# UTC initialisation time explicit in the request, i.e. issue/lead
# provenance is exact. Per Open-Meteo docs, ECMWF IFS HRES single runs
# are archived from 2024-03, all other models from 2026-04-02 - so the
# Single Runs API is the verified route to controlled lead-N snow-depth
# grading from this season onward. The Historical Forecast API carries
# snow_depth for gfs/icon/ecmwf (ukmo: all null) as consecutive
# most-recent model runs (short mixed lead, no per-step issue time),
# scored here under the honest label "recent_run".


def fetch_histforecast_sod(lat: float, lon: float, model: str, start: str,
                           end: str, timezone: str) -> dict[str, float]:
    """Daily snow depth (m) at station-midnight from consecutive recent runs.

    `timezone` must be the station's fixed-offset reporting zone
    (e.g. "Etc/GMT+8"), so T00:00 lands on the same instant as the daily
    SNWD value (see the measurement-contract note at module top)."""
    import json as _json
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    var = f"snow_depth_{model}"
    qs = urlencode({"latitude": lat, "longitude": lon, "start_date": start,
                    "end_date": end, "hourly": "snow_depth", "models": model,
                    "timezone": timezone})
    req = Request(f"{HIST_FORECAST_URL}?{qs}", headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        payload = _json.load(resp)
    hourly = payload.get("hourly", {})
    # single-model responses use the plain variable name; multi-model suffix it
    values = hourly.get("snow_depth", hourly.get(var, []))
    out: dict[str, float] = {}
    for t, v in zip(hourly.get("time", []), values):
        if v is not None and t.endswith("T00:00"):
            out[t[:10]] = float(v)
    return out


SINGLE_RUNS_URL = "https://single-runs-api.open-meteo.com/v1/forecast"
# Station midnight for UTC-8 reporting stations = 08:00 UTC. A run
# initialised at 00:00 UTC on date I therefore serves date I at 8h lead
# and date I+1 at 32h lead, so one call per (model, init day) yields both
# leads for the whole window.
STATION_MIDNIGHT_UTC_HOUR = 8


def fetch_singlerun_hourly(lat: float, lon: float, model: str,
                           init_date: str, forecast_days: int = 2
                           ) -> dict[str, float]:
    """MANUAL ONLY: hourly snow_depth (m, UTC) from one archived model run.

    `init_date` is the run's UTC initialisation day (00:00 UTC init);
    exact issue/lead provenance - the run= parameter pins the run.
    """
    import json as _json
    from urllib.parse import urlencode
    var = f"snow_depth_{model}"
    qs = urlencode({"latitude": lat, "longitude": lon, "hourly": "snow_depth",
                    "models": model, "run": f"{init_date}T00:00",
                    "forecast_days": forecast_days, "timezone": "UTC"})
    req = Request(f"{SINGLE_RUNS_URL}?{qs}", headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        payload = _json.load(resp)
    hourly = payload.get("hourly", {})
    values = hourly.get("snow_depth", hourly.get(var, []))
    return {t: float(v) for t, v in zip(hourly.get("time", []), values)
            if v is not None}


def run_snotel_leads_live(resort: str, past_days: int, output_dir,
                          leads_h: tuple = (8, 32)) -> list:
    """MANUAL ONLY: controlled-lead snow-depth grading vs SNOTEL.

    For each date D the valid instant is station midnight (08:00 UTC);
    each (model, lead) series uses only archived runs initialised exactly
    lead hours before the valid instant (00:00 UTC inits), so issue/lead
    provenance is exact per value. This is the controlled lead-N route
    the recent_run label could not provide.
    """
    import json
    from datetime import date, datetime, timedelta, timezone
    from pathlib import Path
    from .grade import LOCATIONS, score_series, persistence_baseline

    st = RESORT_STATIONS[resort]
    loc = LOCATIONS[resort]
    end = date.today() - timedelta(days=1)
    dates = [(end - timedelta(days=k)).isoformat()
             for k in range(past_days - 1, -1, -1)]
    actual = fetch_snwd_daily(st["triplet"], dates[0], dates[-1])
    rows = []
    for model in ("gfs_seamless", "icon_seamless", "ecmwf_ifs025"):
        runs: dict[str, dict[str, float]] = {}
        for lead in leads_h:
            pred: dict[str, float] = {}
            provenance: dict[str, dict[str, str]] = {}
            for d in dates:
                init = (date.fromisoformat(d)
                        - timedelta(hours=lead - STATION_MIDNIGHT_UTC_HOUR)
                        ).isoformat()
                if init not in runs:
                    runs[init] = fetch_singlerun_hourly(
                        loc["lat"], loc["lon"], model, init)
                valid = f"{d}T{STATION_MIDNIGHT_UTC_HOUR:02d}:00"
                if valid in runs[init]:
                    pred[d] = runs[init][valid]
                    provenance[d] = {"init": f"{init}T00:00Z",
                                     "valid": valid + "Z"}
            row = {"model": model, "lead": f"lead_{lead}h",
                   **score_series(pred, actual)}
            row["provenance"] = provenance
            rows.append(row)
    base = persistence_baseline(actual, 1)
    rows.append({"model": "persistence_1d", "lead": "baseline",
                 **score_series(base, actual)})
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"grading_{resort}_snow-depth-snotel-leads_{end.isoformat()}.json"
    out_path.write_text(json.dumps({
        "resort": resort, "station": st, "variable": "snow_depth",
        "basis": "forecast: model grid-cell snow_depth at station midnight "
                 "(08:00 UTC for this UTC-8 reporting station) from archived "
                 "Single Runs API runs initialised exactly lead hours "
                 "earlier (00:00 UTC inits; per-date init/valid provenance "
                 "recorded per row); actual: SNOTEL SNWD daily value, the "
                 "same instant. Same variable/instant/units; grid cell vs "
                 "on-mountain pillow basis difference still applies.",
        "archive_limits": "Single Runs API snow_depth verified non-null "
                          "2026-11-25 for gfs/icon/ecmwf; per Open-Meteo "
                          "docs, ECMWF IFS HRES runs archived from 2024-03, "
                          "other models from 2026-04-02.",
        "actual_window": [dates[0], dates[-1]],
        "pull_utc": datetime.now(timezone.utc).isoformat(),
        "rows": rows}, indent=2))
    return rows


def run_snotel_live(resort: str, past_days: int, output_dir) -> list:
    """MANUAL ONLY: grade forecast snow DEPTH vs SNOTEL start-of-day depth.

    Matched variable both sides (snow depth, meters, start-of-day).
    Forecast side is the Historical Forecast API (recent-run mixed lead,
    see module note); actual side is the SNOTEL pillow. Grid cell vs
    on-mountain pillow is a real basis difference, recorded in output.
    """
    import json
    from datetime import date, timedelta
    from pathlib import Path
    from .grade import LOCATIONS, score_series, persistence_baseline

    st = RESORT_STATIONS[resort]
    loc = LOCATIONS[resort]
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=past_days + 1)
    actual = fetch_snwd_daily(st["triplet"], start.isoformat(), end.isoformat())
    rows = []
    for model in ("gfs_seamless", "icon_seamless", "ecmwf_ifs025"):
        pred = fetch_histforecast_sod(loc["lat"], loc["lon"], model,
                                      start.isoformat(), end.isoformat(), st["tz"])
        row = {"model": model, "lead": "recent_run", **score_series(pred, actual)}
        rows.append(row)
    base = persistence_baseline(actual, 1)
    rows.append({"model": "persistence_1d", "lead": "baseline",
                 **score_series(base, actual)})
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"grading_{resort}_snow-depth-snotel_{end.isoformat()}.json"
    out_path.write_text(json.dumps({
        "resort": resort, "station": st, "variable": "snow_depth",
        "basis": "forecast: model grid-cell snow_depth at station midnight "
                 "(fixed UTC-8 reporting zone = 08:00 UTC), consecutive "
                 "most-recent runs (short mixed lead, no per-step issue "
                 "time; previous-runs API retains no snow_depth, verified "
                 "all-null 2026-11-24); actual: SNOTEL SNWD daily value, "
                 "the same 08:00 UTC instant (header 'Start of Day "
                 "Values', daily[D]==hourly[D 00:00] verified at 842). "
                 "Same variable/instant/units; different location basis "
                 "(grid cell vs on-mountain pillow).",
        "actual_window": [start.isoformat(), end.isoformat()],
        "forecast_source": "open-meteo historical-forecast API (recent runs)",
        "actual_source": "USDA NRCS SNOTEL report generator (physical station)",
        "rows": rows,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rows
