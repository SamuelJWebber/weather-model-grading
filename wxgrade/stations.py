"""Cross-check model grading against real ASOS station observations.

Removes the reanalysis self-verification caveat: instead of verifying model
forecasts against the Open-Meteo archive (which itself contains ECMWF IFS),
this verifies them against a physical airport station thermometer.

Source: Iowa State IEM ASOS download service (free, no key), hourly METAR
observations for station NYC = Central Park (KNYC). Network access is MANUAL
ONLY via fetch_station_daily_max; tests run offline on CSV fixtures.
"""

from __future__ import annotations

import argparse
import csv
import io
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen

IEM_ASOS_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
USER_AGENT = "weather-model-grading/0.2.0 (personal research)"
SOURCE_NOTE = "Iowa State IEM ASOS service, station NYC (KNYC Central Park), hourly METAR"


def parse_asos_csv_detailed(text: str) -> tuple[dict[str, float], dict[str, int]]:
    """Daily max tmpf per local date AND per-day observation counts.

    The counts make the README coverage claim ("24-25 obs/day, zero
    missing hours") re-derivable from the saved artifact (builder audit
    2026-11-25, finding 4)."""
    daily: dict[str, float] = {}
    counts: dict[str, int] = {}
    for row in csv.DictReader(io.StringIO(text)):
        tmp = (row.get("tmpf") or "").strip()
        valid = (row.get("valid") or "").strip()
        if not tmp or tmp == "M" or not valid:
            continue
        day = valid[:10]
        counts[day] = counts.get(day, 0) + 1
        daily[day] = max(daily.get(day, float("-inf")), float(tmp))
    return daily, counts


def parse_asos_csv(text: str) -> dict[str, float]:
    """Daily max tmpf per local date from IEM ASOS CSV (station,valid,tmpf)."""
    return parse_asos_csv_detailed(text)[0]


def fetch_station_daily_max(station: str, start: date, end: date) -> dict[str, float]:
    """MANUAL ONLY: pull hourly ASOS obs and reduce to daily maxima."""
    qs = urlencode({
        "station": station, "data": "tmpf",
        "year1": start.year, "month1": start.month, "day1": start.day,
        "year2": end.year, "month2": end.month, "day2": end.day,
        "tz": "America/New_York", "format": "onlycomma", "latlon": "no",
        "elev": "no", "missing": "M", "trace": "T", "direct": "no",
        "report_type": "3",
    })
    req = Request(f"{IEM_ASOS_URL}?{qs}", headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=90) as resp:
        return parse_asos_csv(resp.read().decode("utf-8", errors="replace"))


def fetch_station_daily_max_detailed(station: str, start: date, end: date):
    """MANUAL ONLY: hourly ASOS obs -> (daily maxima, per-day obs counts)."""
    qs = urlencode({
        "station": station, "data": "tmpf",
        "year1": start.year, "month1": start.month, "day1": start.day,
        "year2": end.year, "month2": end.month, "day2": end.day,
        "tz": "America/New_York", "format": "onlycomma", "latlon": "no",
        "elev": "no", "missing": "M", "trace": "T", "direct": "no",
        "report_type": "3",
    })
    req = Request(f"{IEM_ASOS_URL}?{qs}", headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=90) as resp:
        return parse_asos_csv_detailed(resp.read().decode("utf-8", errors="replace"))


def compare_forecasts_to_station(
    forecasts: Mapping[tuple[str, int], Mapping[str, float]],
    station_actual: Mapping[str, float],
) -> list[dict[str, Any]]:
    """Score each (model, lead) against station observations."""
    from .grade import score_series

    rows: list[dict[str, Any]] = []
    for (model, lead), pred in sorted(forecasts.items()):
        rows.append({"model": model, "lead_days": lead, **score_series(pred, station_actual)})
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Pull live data (manual; never in tests).")
    parser.add_argument("--station", default="NYC")
    parser.add_argument("--lat", type=float, default=40.71)
    parser.add_argument("--lon", type=float, default=-74.01)
    parser.add_argument("--past-days", type=int, default=30)
    parser.add_argument("--output-dir", default="results")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("only --live is supported; tests exercise pure functions offline")

    from .grade import LEADS, MODELS, fetch_model_lead_max

    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=args.past_days + max(LEADS))
    station_actual, obs_per_day = fetch_station_daily_max_detailed(
        args.station, start, end)
    forecasts: dict[tuple[str, int], dict[str, float]] = {}
    for model in MODELS:
        for lead in LEADS:
            forecasts[(model, lead)] = fetch_model_lead_max(args.lat, args.lon, model, lead, args.past_days)
    rows = compare_forecasts_to_station(forecasts, station_actual)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"station_verification_{args.station}_{end.isoformat()}.json"
    out_path.write_text(
        __import__("json").dumps({
            "station": args.station, "station_source": SOURCE_NOTE,
            "past_days": args.past_days, "station_days": len(station_actual),
            "station_obs_per_day": obs_per_day,
            "rows": rows,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"{'model':<18}{'lead':>5}{'n':>4}{'MAE':>7}{'RMSE':>7}{'bias':>7}")
    for r in rows:
        print(f"{r['model']:<18}{r['lead_days']:>5}{r['n']:>4}{r['mae']:>7}{r['rmse']:>7}{r['bias']:>7}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
