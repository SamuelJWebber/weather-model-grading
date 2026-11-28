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
import gzip
import hashlib
import json
import math
import os
import tempfile
from datetime import date, datetime, timedelta, timezone as utc_zone
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
    timezone: str = "America/New_York", forecast_days: int = 1, *, fetch=None,
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
    payload = (fetch or fetch_json)(f"{PREVIOUS_RUNS_URL}?{qs}")
    return _daily_forecast(payload, var, reduce)


def _daily_forecast(payload, var, reduce):
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
        elif reduce == "sod":
            # start-of-day value only (00:00 local), matching SNOTEL SNWD basis
            if t.endswith("T00:00"):
                daily[day] = float(v)
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
                       timezone: str = "America/New_York", *, fetch=None) -> dict[str, float]:
    qs = urlencode({
        "latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
        "daily": daily_var, "temperature_unit": "fahrenheit",
        "timezone": timezone,
    })
    payload = (fetch or fetch_json)(f"{ARCHIVE_URL}?{qs}")
    return _daily_observations(payload, daily_var)


def _daily_observations(payload, daily_var):
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
    """Compare each forecast to persistence on the same target dates.

    forecast_n counts model/actual matches before requiring a lagged actual.
    n and every loss in a score row use the dates listed in paired_dates.
    """
    rows: list[dict[str, Any]] = []
    for (model, lead), pred in sorted(forecasts.items()):
        available = pred.keys() & actual.keys()
        base = persistence_baseline(actual, lead)
        dates = sorted(available & base.keys())
        paired_actual = {day: actual[day] for day in dates}
        rows.append({
            "model": model, "lead_days": lead, "forecast_n": len(available),
            "paired_dates": dates, **score_series(pred, paired_actual),
            "persistence_mae": score_series(base, paired_actual)["mae"],
        })
    return rows


def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def replay_receipt(path):
    """Recompute saved scores from the original hourly forecasts and daily actuals."""
    path = Path(path)
    compressed = path.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != path.stem.split(".")[0]:
        raise ValueError("input receipt SHA-256 differs from its filename")
    receipt = json.loads(gzip.decompress(compressed))
    if receipt["format"] != "wxgrade-daily-inputs-v1":
        raise ValueError("unsupported daily input receipt format")
    forecasts = {}
    for record in receipt["forecasts"]:
        key = (record["model"], record["lead_days"])
        if key in forecasts:
            raise ValueError(f"duplicate model/lead response: {key}")
        series = f'{receipt["variable"]}_previous_day{record["lead_days"]}'
        forecasts[key] = _daily_forecast(record["response"], series, receipt["reduce"])
    actual = _daily_observations(receipt["observations"]["response"], receipt["daily_variable"])
    rows = grade(forecasts, actual)
    if rows != receipt["rows"]:
        raise ValueError("replayed scores differ from the scores recorded at collection time")
    return rows


def run_live(lat: float, lon: float, past_days: int, output_dir: Path | str,
             variable: str = "temperature_2m", reduce: str = "max",
             daily_var: str = "temperature_2m_max",
             timezone: str = "America/New_York", label: str = "") -> list[dict[str, Any]]:
    """MANUAL ONLY: pull forecasts + actuals and grade all model/lead pairs."""
    records = []
    def capture(url):
        response = fetch_json(url)
        records.append({"url": url, "received_utc": datetime.now(utc_zone.utc).isoformat(), "response": response})
        return response

    forecasts = {}
    for model in MODELS:
        for lead in LEADS:
            forecasts[model, lead] = fetch_model_lead_daily(
                lat, lon, model, lead, past_days, variable=variable, reduce=reduce, timezone=timezone, fetch=capture)
            records[-1].update(model=model, lead_days=lead)
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=past_days + max(LEADS))
    actual = fetch_actual_daily(lat, lon, start.isoformat(), end.isoformat(),
                                daily_var=daily_var, timezone=timezone, fetch=capture)
    rows = grade(forecasts, actual)
    out_dir = Path(output_dir)
    tag = variable.replace("_2m", "").replace("_", "-")
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or f"{lat}-{lon}"
    out_path = out_dir / f"grading_{slug}_{tag}_{end.isoformat()}.json"
    summary = {
        "location": {"lat": lat, "lon": lon, "label": label, "timezone": timezone},
        "variable": variable, "reduce": reduce, "daily_variable": daily_var, "past_days": past_days,
        "actual_window": [start.isoformat(), end.isoformat()],
        "actual_source": "open-meteo archive (ERA5/best_match analysis)",
        "forecast_source": "open-meteo previous-runs API (archived model runs)",
        "rows": rows,
    }
    receipt = {**summary, "format": "wxgrade-daily-inputs-v1", "forecasts": records[:-1],
               "observations": records[-1], "attribution": "Open-Meteo, CC BY 4.0"}
    compressed = gzip.compress(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode(), mtime=0)
    digest = hashlib.sha256(compressed).hexdigest()
    relative = Path("raw") / "daily-inputs" / f"{digest}.json.gz"
    _atomic_write(out_dir / relative, compressed)
    summary["input_receipt"] = {"path": relative.as_posix(), "sha256": digest}
    _atomic_write(out_path, (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode())
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true", help="Pull data and save a content-addressed input receipt.")
    mode.add_argument("--replay", type=Path, metavar="RECEIPT", help="Regrade a saved .json.gz receipt offline.")
    parser.add_argument("--location", choices=sorted(LOCATIONS), default="nyc",
                        help="Named location; overrides --lat/--lon and sets timezone.")
    parser.add_argument("--lat", type=float, default=None)
    parser.add_argument("--lon", type=float, default=None)
    parser.add_argument("--variable", default="temperature_2m",
                        help="Hourly base variable, e.g. temperature_2m or snowfall.")
    parser.add_argument("--past-days", type=int, default=30)
    parser.add_argument("--output-dir", default="results")
    args = parser.parse_args(argv)
    if args.replay:
        rows = replay_receipt(args.replay)
    else:
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
    print(f"{'model':<18}{'lead':>5}{'available':>10}{'paired':>8}{'MAE':>7}{'RMSE':>7}{'bias':>7}{'persistMAE':>11}")
    for r in rows:
        counts = f"{r['model']:<18}{r['lead_days']:>5}{r['forecast_n']:>10}{r['n']:>8}"
        if r["n"] == 0:
            print(f"{counts}  no paired data")
            continue
        print(f"{counts}{r['mae']:>7}{r['rmse']:>7}{r['bias']:>7}{r['persistence_mae']:>11}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
