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
             "tz": "America/Denver", "note": "on-mountain, 2495m"},
    "breckenridge": {"triplet": "531:CO:SNTL", "name": "Hoosier Pass",
                     "tz": "America/Denver",
                     "note": "39.36,-106.06 at 11600ft, ~13km south; nearest by "
                             "distance is Copper Mountain (415) at ~9km/10500ft "
                             "but that pillow sits on a different resort's terrain"},
    "park_city": {"triplet": "814:UT:SNTL", "name": "Thaynes Canyon",
                  "tz": "America/Denver",
                  "note": "40.62,-111.53 at 9260ft, ~4km; on resort terrain"},
    "palisades": {"triplet": "784:CA:SNTL", "name": "Palisades Tahoe",
                  "tz": "America/Los_Angeles",
                  "note": "39.18,-120.27 at 8010ft, ~3km; named for the resort"},
    # NOT covered (verified 2026-11-24/25): stowe (no SNOTEL in VT; NWS COOP
    # on Mount Mansfield is the alternative, not integrated), whistler (BC),
    # zermatt (CH) - need national networks, unverified.
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
# (snow_depth_previous_dayN all-null for all four graded models), so
# controlled lead-N snow-depth scoring is an UNRESOLVED problem (one
# verified route: accumulate current-run forecasts daily going forward;
# other archive sources not ruled out). The Historical Forecast API DOES
# carry snow_depth for gfs/icon/ecmwf (ukmo: all null) - genuine
# consecutive most-recent model runs, i.e. short mixed lead (~0-24h),
# scored here under the honest label "recent_run".


def fetch_histforecast_sod(lat: float, lon: float, model: str, start: str,
                           end: str, timezone: str) -> dict[str, float]:
    """Daily 00:00-local snow depth (m) from consecutive recent runs."""
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
        "basis": "forecast: model grid-cell snow_depth at 00:00 local (m), "
                 "consecutive most-recent runs (mixed ~0-24h lead, NOT "
                 "controlled lead-N; previous-runs API retains no snow_depth, "
                 "verified all-null 2026-11-24); actual: SNOTEL SNWD "
                 "start-of-day snow pillow (in->m). Same variable, different "
                 "location basis (grid cell vs on-mountain pillow).",
        "actual_window": [start.isoformat(), end.isoformat()],
        "forecast_source": "open-meteo historical-forecast API (recent runs)",
        "actual_source": "USDA NRCS SNOTEL report generator (physical station)",
        "rows": rows,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rows
