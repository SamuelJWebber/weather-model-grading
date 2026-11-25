"""Grade weather forecast models on real archived forecasts vs actuals.

Data sources (both free, no key, CC BY 4.0 data from Open-Meteo):
- Previous Runs API: hourly values from model runs issued N days earlier
  (`temperature_2m_previous_dayN`), i.e. genuine lead-N forecasts.
- Archive API: daily actuals (ERA5/best_match analysis; recent days may use
  short-range forecast fill - see README caveat).

Network access is MANUAL ONLY via the CLI; tests run offline on fixtures.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date, timedelta
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
USER_AGENT = "weather-model-grading/0.1.0 (personal research)"
MODELS = ("gfs_seamless", "ecmwf_ifs025", "icon_seamless", "ukmo_seamless")
LEADS = (1, 3, 5)

# Named scoring locations. Mountains are configurable defaults for the
# ski-trip use case (Epic/Ikon destination resorts plus Zermatt, which Sam is
# actively evaluating); swap or extend freely.
LOCATIONS = {
    "nyc": {"tz": "America/New_York", "lat": 40.71, "lon": -74.01, "label": "New York City"},
    "vail": {"tz": "America/Denver", "lat": 39.64, "lon": -106.37, "label": "Vail, CO (Epic)"},
    "breckenridge": {"tz": "America/Denver", "lat": 39.48, "lon": -106.07, "label": "Breckenridge, CO (Epic)"},
    "park_city": {"tz": "America/Denver", "lat": 40.65, "lon": -111.51, "label": "Park City, UT (Epic)"},
    "whistler": {"tz": "America/Los_Angeles", "lat": 50.12, "lon": -122.95, "label": "Whistler, BC (Epic)"},
    "stowe": {"tz": "America/New_York", "lat": 44.47, "lon": -72.69, "label": "Stowe, VT (Epic)"},
    "palisades": {"tz": "America/Los_Angeles", "lat": 39.20, "lon": -120.24, "label": "Palisades Tahoe, CA (Ikon)"},
    "zermatt": {"tz": "Europe/Zurich", "lat": 46.02, "lon": 7.75, "label": "Zermatt, CH (active search)"},
}


def fetch_json(url: str) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        return json.load(resp)


def fetch_model_lead_daily(
    lat: float, lon: float, model: str, lead: int, past_days: int,
    variable: str = "temperature_2m", reduce: str = "max",
    timezone: str = "America/New_York", forecast_days: int = 1,
) -> dict[str, float]:
    """Predicted daily aggregate per date from runs issued `lead` days before.

    variable: any hourly variable the Previous Runs API exposes as
    `<variable>_previous_dayN` (e.g. temperature_2m, snowfall).
    reduce: "max" for daily high, "sum" for daily snowfall totals.
    """
    var = f"{variable}_previous_day{lead}"
    qs = urlencode({
        "latitude": lat, "longitude": lon, "hourly": var, "models": model,
        "temperature_unit": "fahrenheit", "past_days": past_days,
        "forecast_days": forecast_days, "timezone": timezone,
    })
    payload = fetch_json(f"{PREVIOUS_RUNS_URL}?{qs}")
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    values = hourly.get(var, [])
    daily: dict[str, float] = {}
    for t, v in zip(times, values):
        if v is None:
            continue
        day = t[:10]
        if reduce == "sum":
            daily[day] = daily.get(day, 0.0) + float(v)
        else:
            daily[day] = max(daily.get(day, float("-inf")), float(v))
    return daily


def fetch_model_lead_max(
    lat: float, lon: float, model: str, lead: int, past_days: int, forecast_days: int = 1
) -> dict[str, float]:
    """Predicted daily max temp per date from runs issued `lead` days before."""
    return fetch_model_lead_daily(lat, lon, model, lead, past_days,
                                  variable="temperature_2m", reduce="max",
                                  forecast_days=forecast_days)


def fetch_actual_daily(lat: float, lon: float, start: str, end: str,
                       daily_var: str = "temperature_2m_max",
                       timezone: str = "America/New_York") -> dict[str, float]:
    qs = urlencode({
        "latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
        "daily": daily_var, "temperature_unit": "fahrenheit",
        "timezone": timezone,
    })
    payload = fetch_json(f"{ARCHIVE_URL}?{qs}")
    daily = payload.get("daily", {})
    return {
        d: float(v) for d, v in zip(daily.get("time", []), daily.get(daily_var, []))
        if v is not None
    }


def fetch_actual_max(lat: float, lon: float, start: str, end: str) -> dict[str, float]:
    return fetch_actual_daily(lat, lon, start, end)


def persistence_baseline(actual: Mapping[str, float], lead: int) -> dict[str, float]:
    """Actual value `lead` days earlier as the no-skill forecast."""
    days = sorted(actual)
    out: dict[str, float] = {}
    for d in days:
        prev = (date.fromisoformat(d) - timedelta(days=lead)).isoformat()
        if prev in actual:
            out[d] = actual[prev]
    return out


def score_series(pred: Mapping[str, float], actual: Mapping[str, float]) -> dict[str, Any]:
    """MAE, RMSE, bias and n over dates present in both series."""
    errs = [pred[d] - actual[d] for d in sorted(pred) if d in actual]
    if not errs:
        return {"n": 0, "mae": None, "rmse": None, "bias": None}
    n = len(errs)
    mae = sum(abs(e) for e in errs) / n
    rmse = math.sqrt(sum(e * e for e in errs) / n)
    return {"n": n, "mae": round(mae, 3), "rmse": round(rmse, 3), "bias": round(sum(errs) / n, 3)}


def grade(
    forecasts: Mapping[tuple[str, int], Mapping[str, float]],
    actual: Mapping[str, float],
    leads: Sequence[int] = LEADS,
) -> list[dict[str, Any]]:
    """One score row per (model, lead), plus persistence rows per lead."""
    rows: list[dict[str, Any]] = []
    for (model, lead), pred in sorted(forecasts.items()):
        row = {"model": model, "lead_days": lead, **score_series(pred, actual)}
        base = persistence_baseline(actual, lead)
        row["persistence_mae"] = score_series(base, actual)["mae"]
        rows.append(row)
    return rows


def run_live(lat: float, lon: float, past_days: int, output_dir: Path | str,
             variable: str = "temperature_2m", reduce: str = "max",
             daily_var: str = "temperature_2m_max",
             timezone: str = "America/New_York", label: str = "") -> list[dict[str, Any]]:
    """MANUAL ONLY: pull forecasts + actuals and grade all model/lead pairs."""
    forecasts: dict[tuple[str, int], dict[str, float]] = {}
    for model in MODELS:
        for lead in LEADS:
            forecasts[(model, lead)] = fetch_model_lead_daily(
                lat, lon, model, lead, past_days,
                variable=variable, reduce=reduce, timezone=timezone)
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=past_days + max(LEADS))
    actual = fetch_actual_daily(lat, lon, start.isoformat(), end.isoformat(),
                                daily_var=daily_var, timezone=timezone)
    rows = grade(forecasts, actual)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = variable.replace("_2m", "").replace("_", "-")
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or f"{lat}-{lon}"
    out_path = out_dir / f"grading_{slug}_{tag}_{end.isoformat()}.json"
    out_path.write_text(json.dumps({
        "location": {"lat": lat, "lon": lon, "label": label, "timezone": timezone},
        "variable": variable, "reduce": reduce,
        "past_days": past_days,
        "actual_window": [start.isoformat(), end.isoformat()],
        "actual_source": "open-meteo archive (ERA5/best_match analysis)",
        "forecast_source": "open-meteo previous-runs API (archived model runs)",
        "rows": rows,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Pull live data (manual; never in tests).")
    parser.add_argument("--location", choices=sorted(LOCATIONS), default="nyc",
                        help="Named location; overrides --lat/--lon and sets timezone.")
    parser.add_argument("--lat", type=float, default=None)
    parser.add_argument("--lon", type=float, default=None)
    parser.add_argument("--variable", default="temperature_2m",
                        help="Hourly base variable, e.g. temperature_2m or snowfall.")
    parser.add_argument("--past-days", type=int, default=30)
    parser.add_argument("--output-dir", default="results")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("only --live is supported; tests exercise pure functions offline")
    loc = LOCATIONS[args.location]
    lat = args.lat if args.lat is not None else loc["lat"]
    lon = args.lon if args.lon is not None else loc["lon"]
    if args.variable == "snowfall":
        reduce, daily_var = "sum", "snowfall_sum"
    else:
        reduce, daily_var = "max", f"{args.variable}_max"
    rows = run_live(lat, lon, args.past_days, args.output_dir,
                    variable=args.variable, reduce=reduce, daily_var=daily_var,
                    timezone=loc["tz"], label=loc["label"])
    print(f"{'model':<18}{'lead':>5}{'n':>4}{'MAE':>7}{'RMSE':>7}{'bias':>7}{'persistMAE':>11}")
    for r in rows:
        if r["n"] == 0:
            print(f"{r['model']:<18}{r['lead_days']:>5}{'no data':>12}")
            continue
        print(f"{r['model']:<18}{r['lead_days']:>5}{r['n']:>4}{r['mae']:>7}{r['rmse']:>7}"
              f"{r['bias']:>7}{r['persistence_mae']:>11}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
