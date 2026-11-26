"""Forecast-time observation log: snapshot what each actuals source shows
RIGHT NOW, with the real retrieval timestamp and the raw response
preserved.

Purpose (preparation for operational snow-depth validation): the paired
artifacts are retrospective - actuals were pulled days after their valid
instants, so they cannot show what a forecaster could have seen at issue
time. This log fixes that going forward: each run records fetch_utc (the
true retrieval instant), the raw response bytes (sha256), and the newest
data timestamp inside the response. availability_lag = fetch_utc minus
newest data instant is the empirical "what was available when" measurement
that the archive alone cannot provide later.

This script is MANUAL ONLY. Running it on a cadence is a separate
decision (see the cadence/limitations report); it creates no schedules.

Sources match the grading routes exactly (no new dependencies):
  SNOTEL stations -> NRCS report generator, hourly SNWD, last 3 days.
  MMNV1 COOP      -> IEM daily.py, snowd_in, last 7 days (daily-only
                     observer; no hourly product exists).

Timestamp conventions (verified in-repo):
  SNOTEL hourly "D hh:00" = that clock time + 8h UTC (33/33 match vs the
    daily series at all four stations on 2026-11-26).
  COOP snowd_in[D] = depth at D 21:00 UTC (measurement contract).

Run from repo root: PYTHONPATH=. python3 scripts/observe_now.py
Writes results/raw/obslog/<station>/<fetch_stamp>.<ext> +
appends results/raw/obslog/index.jsonl. Fetch failures are logged as
rows with "error" set - a failed fetch is availability evidence too.
"""
import csv
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, '.')
from wxgrade.snotel import REPORT_URL, USER_AGENT  # noqa: E402
from wxgrade.coop import DAILY_URL  # noqa: E402

OUT = Path('results/raw/obslog')
SNOTEL = ["842:CO:SNTL", "415:CO:SNTL", "1321:UT:SNTL", "834:CA:SNTL"]
COOP = {"station": "MMNV1", "network": "VT_COOP"}
SNOTEL_CSV_TO_UTC_H = 8      # verified convention: csv time + 8h = UTC
COOP_VALID_UTC_H = 21        # contract: snowd_in[D] = depth at D 21:00 UTC


def fetch(url, timeout=45):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def snotel_newest(text):
    newest = None
    for row in csv.reader(text.splitlines()):
        if not row or row[0].startswith('#') or row[0] == 'Date':
            continue
        if len(row) < 2 or row[1].strip() in ('', 'M'):
            continue
        ts = datetime.strptime(row[0], "%Y-%m-%d %H:%M")
        if newest is None or ts > newest:
            newest = ts
    return newest  # station CSV clock; +8h = UTC


def coop_newest(text):
    # IEM daily.py pre-posts recent date rows with value None until data
    # arrives - only rows with an actual value count.
    newest = None
    for row in csv.reader(text.splitlines()):
        if not row or row[0].startswith('#') or row[0].lower() == 'station':
            continue
        try:
            val = row[2].strip()
            if val in ('', 'None', 'M'):
                continue
            float(val)
            d = datetime.strptime(row[1].strip(), "%Y-%m-%d")
        except (ValueError, IndexError):
            continue
        if newest is None or d > newest:
            newest = d
    return newest  # date; valid instant = 21:00 UTC that day


def log_one(station_key, url, parse_newest, to_utc, ext, index):
    fetch_utc = datetime.now(timezone.utc)
    stamp = fetch_utc.strftime("%Y-%m-%dT%H%M%SZ")
    rec = {"station": station_key, "url": url, "fetch_utc":
           fetch_utc.isoformat(timespec="seconds")}
    try:
        raw = fetch(url)
    except Exception as err:  # noqa: BLE001 - failures are evidence
        rec["error"] = f"{type(err).__name__}: {err}"
        index.append(rec)
        print(f"{station_key}: FETCH FAILED {rec['error']}")
        return rec
    rec["bytes"] = len(raw)
    rec["sha256"] = hashlib.sha256(raw).hexdigest()
    d = OUT / station_key.replace(':', '-')
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{stamp}.{ext}"
    path.write_bytes(raw)
    rec["raw_path"] = str(path)
    text = raw.decode("utf-8", errors="replace")
    newest_local = parse_newest(text)
    if newest_local is None:
        rec["newest_data"] = None
        rec["note"] = "no data rows in response"
    else:
        newest_utc = (newest_local.replace(tzinfo=timezone.utc)
                      + timedelta(hours=to_utc))
        rec["newest_data_utc"] = newest_utc.isoformat(timespec="seconds")
        lag = fetch_utc - newest_utc
        rec["availability_lag_hours"] = round(lag.total_seconds() / 3600, 2)
    index.append(rec)
    print(f"{station_key}: newest={rec.get('newest_data_utc')} "
          f"lag_h={rec.get('availability_lag_hours')} sha={rec['sha256'][:12]}")
    return rec


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    index_path = OUT / 'index.jsonl'
    index = []
    end = datetime.now(timezone.utc).date()
    start3 = (end - timedelta(days=3)).isoformat()
    end_s = end.isoformat()
    for triplet in SNOTEL:
        url = REPORT_URL.format(triplet=triplet, start=start3, end=end_s)
        url = url.replace('/daily/', '/hourly/')
        log_one(triplet, url, snotel_newest, SNOTEL_CSV_TO_UTC_H, 'csv',
                index)
    start7 = (end - timedelta(days=7)).isoformat()
    url = (f"{DAILY_URL}?" + urlencode({
        "network": COOP["network"], "stations": COOP["station"],
        "sts": f"{start7}T00:00Z", "ets": f"{end_s}T00:00Z",
        "var": "snowd_in"}))
    log_one(f"coop-{COOP['station']}", url, coop_newest, COOP_VALID_UTC_H,
            'csv', index)
    with open(index_path, 'a', encoding='utf-8') as fh:
        for rec in index:
            fh.write(json.dumps(rec) + "\n")
    print("index appended:", index_path)


if __name__ == "__main__":
    main()
