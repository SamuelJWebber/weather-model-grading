"""Measurement-contract verification with SAVED raw evidence.

The builder audit (docs/audit-2026-11-25.md, finding 5) flagged that
earlier contract checks referenced pulls without saving them. These
verifiers save the raw source responses under results/contracts/ next to
the verdict, so the contract claim is re-derivable from the artifact.

Network access is MANUAL ONLY; tests run offline on fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

USER_AGENT = "weather-model-grading/0.2.0 (personal research)"
IEM_OBHISTORY = "https://mesonet.agron.iastate.edu/api/1/obhistory.json"
NRCS_REPORT = ("https://wcc.sc.egov.usda.gov/reportGenerator/view_csv/"
               "customSingleStationReport")


def parse_obhistory_snow(payload: dict) -> list[dict]:
    """Snow-depth reports (SDIRZZZ, inches) with their UTC valid times."""
    return [{"value_in": r["SDIRZZZ"], "utc_valid": r.get("utc_valid")}
            for r in payload.get("data", [])
            if r.get("SDIRZZZ") is not None]


def coop_contract_verdict(reports: list[dict], expect_hour_utc: int = 21
                          ) -> dict:
    """Verdict on 'snow depth reports once daily at exactly HH:00 UTC'."""
    hours = sorted({(r["utc_valid"] or "")[11:13]
                    for r in reports if r.get("utc_valid")})
    once = len(reports) == 1
    at_hour = hours == [f"{expect_hour_utc:02d}"]
    return {"n_reports": len(reports), "report_hours_utc": hours,
            "reports_once_daily": once, "at_expected_hour": at_hour,
            "contract_holds": bool(once and at_hour)}


def verify_coop_contract(station: str, network: str, day: str,
                         out_dir: str = "results/contracts") -> dict:
    """MANUAL ONLY: pull one day's raw obhistory, save it, verdict."""
    qs = urlencode({"station": station, "network": network, "date": day,
                    "full": "1"})
    req = Request(f"{IEM_OBHISTORY}?{qs}", headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    raw_path = out / f"coop_{station}_{day}_obhistory.json"
    raw_path.write_text(json.dumps(payload))
    reports = parse_obhistory_snow(payload)
    verdict = {"station": station, "network": network, "day": day,
               "raw_evidence": str(raw_path),
               "snow_reports": reports,
               **coop_contract_verdict(reports)}
    (out / f"coop_{station}_{day}_verdict.json").write_text(
        json.dumps(verdict, indent=2))
    return verdict


def parse_nrcs_hourly_midnight(daily_csv: str, hourly_csv: str, day: str
                               ) -> dict:
    """Compare daily SNWD[day] to the hourly value at day 00:00."""
    import csv as _csv
    import io

    def rows(text):
        lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
        return list(_csv.reader(io.StringIO("\n".join(lines))))

    daily = {r[0].strip(): r[1].strip() for r in rows(daily_csv)
             if len(r) >= 2 and r[0].strip()[:4].isdigit()}
    hourly = {r[0].strip(): r[1].strip() for r in rows(hourly_csv)
              if len(r) >= 2 and r[0].strip()[:4].isdigit()}
    d_val = daily.get(day)
    h_val = hourly.get(f"{day} 00:00")
    return {"day": day, "daily_value": d_val, "hourly_00_value": h_val,
            "matches": d_val is not None and d_val == h_val}


def verify_snotel_contract(triplet: str, day: str,
                           out_dir: str = "results/contracts") -> dict:
    """MANUAL ONLY: pull recent daily + hourly SNWD, save raw, compare
    daily[day] to hourly[day 00:00] (station-midnight contract)."""
    from datetime import date as _date, timedelta as _td
    d0 = (_date.fromisoformat(day) - _td(days=1)).isoformat()
    d1 = (_date.fromisoformat(day) + _td(days=1)).isoformat()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    texts = {}
    for freq in ("daily", "hourly"):
        # explicit day+/-1 window: the relative -N,0 form only reaches
        # back ~24h on the hourly report (verified 2026-11-26)
        url = (f"{NRCS_REPORT}/{freq}/{triplet.replace(':', '%3A')}"
               f"%7Cid=%22%22%7Cname/{d0},{d1}/SNWD::value")
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=60) as resp:
            texts[freq] = resp.read().decode("utf-8", errors="replace")
        (out / f"snotel_{triplet.replace(':', '-')}_{day}_{freq}.csv"
         ).write_text(texts[freq])
    verdict = {"triplet": triplet,
               "raw_evidence": [str(p) for p in sorted(out.glob(
                   f"snotel_{triplet.replace(':', '-')}_{day}_*.csv"))],
               **parse_nrcs_hourly_midnight(texts["daily"], texts["hourly"],
                                            day)}
    (out / f"snotel_{triplet.replace(':', '-')}_{day}_verdict.json"
     ).write_text(json.dumps(verdict, indent=2))
    return verdict
