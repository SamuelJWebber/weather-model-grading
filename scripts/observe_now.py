"""Forecast-time observation log: snapshot what each actuals source shows
RIGHT NOW, with the real retrieval timestamps and the raw response
preserved.

Purpose (preparation for operational snow-depth validation): the paired
artifacts are retrospective - actuals were pulled days after their valid
instants, so they cannot show what a forecaster could have seen at issue
time. This log fixes that going forward: each run records when the request
started and when the response finished, the raw response bytes (sha256),
and the newest data timestamp inside the response. availability_lag =
response_complete_utc minus newest data instant is the empirical "what was
available when" measurement that the archive alone cannot provide later.

This script is MANUAL ONLY. Running it on a cadence is a separate
decision (see docs/obslog-pilot-handoff.md); it creates no schedules.

Sources match the grading routes exactly (no new dependencies):
  SNOTEL stations -> NRCS report generator, hourly SNWD, last 3 days.
  MMNV1 COOP      -> IEM daily.py, snowd_in, window ending tomorrow
                     (daily-only observer; no hourly product exists).

Timestamp conventions:
  SNOTEL hourly CSV carries no timezone. NRCS AWDB documentation states
  SNOTEL (SNTL network) hourly measurements are recorded in Pacific
  Standard Time (UTC-8, year-round), with "a few stations in Alaska and
  elsewhere" recorded in station local time
  (https://opencdss.state.co.us/tstool/latest/doc-user/datastore-ref/NRCS-AWDB/NRCS-AWDB/
   mirroring NRCS AWDB docs). PROVISIONAL for these four stations: the
  doc's "elsewhere" exception cannot be excluded from documentation
  alone, and the in-repo 33/33 daily-vs-hourly anchor
  (scripts/hourly_persistence_snotel_check.py) verifies date-boundary
  assignment only, not whole-hours offsets within a day. Every
  availability_lag value this script writes inherits that caveat pending
  station-specific metadata (e.g., AWDB station timeZone field) or
  varying-value sub-daily evidence.
  COOP snowd_in[D] = depth at D 21:00 UTC (measurement contract).
  IEM daily.py `ets` is an inclusive end DATE (date-only form in the
  service docs: https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py?help=).
  The window ends TOMORROW so nothing already filed can be censored; a
  future end date is harmless (the service returns only existing rows).

Persistence guarantees: each source's raw bytes are written before its
index row, and each index row is appended+flushed immediately after that
source finishes. A fetch or parse failure on one source is logged as its
own row (failures are availability evidence) and never loses or blocks
evidence for the other sources.

Run from repo root: python3 scripts/observe_now.py
(or from anywhere with --out-dir; stdlib-only, no repo checkout needed)
"""
import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

USER_AGENT = "weather-model-grading/0.1.0 (personal research)"
REPORT_URL = (
    "https://wcc.sc.egov.usda.gov/reportGenerator/view_csv/"
    "customSingleStationReport/hourly/{triplet}%7Cid=%22%22%7Cname/"
    "{start},{end}/SNWD::value")
DAILY_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py"

SNOTEL = ["842:CO:SNTL", "415:CO:SNTL", "1321:UT:SNTL", "834:CA:SNTL"]
COOP = {"station": "MMNV1", "network": "VT_COOP"}
SNOTEL_CSV_TO_UTC_H = 8      # PROVISIONAL: PST per NRCS AWDB docs ("Alaska/elsewhere"
                       # exception unresolved); date-boundary anchored 33/33 in-repo
COOP_VALID_UTC_H = 21        # contract: snowd_in[D] = depth at D 21:00 UTC


def build_requests(now):
    """Pure request list - regression-tested so the windows always cover
    everything currently available (no window-censoring repeat)."""
    start3 = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    reqs = [(t, REPORT_URL.format(triplet=t, start=start3, end=end),
             snotel_newest, SNOTEL_CSV_TO_UTC_H, "csv") for t in SNOTEL]
    coop_url = DAILY_URL + "?" + urlencode({
        "network": COOP["network"], "stations": COOP["station"],
        "sts": (now - timedelta(days=7)).strftime("%Y-%m-%d"),
        "ets": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
        "var": "snowd_in"})
    reqs.append((f"coop-{COOP['station']}", coop_url, coop_newest,
                 COOP_VALID_UTC_H, "csv"))
    return reqs


def fetch(url, timeout=45):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _data_rows(text):
    for row in csv.reader(text.splitlines()):
        if not row or row[0].startswith('#'):
            continue
        yield row


def snotel_newest(text):
    newest = None
    for row in _data_rows(text):
        if row[0] == 'Date' or len(row) < 2:
            continue
        try:
            val = float(row[1].strip())
        except ValueError:
            continue  # 'M', '', None rows
        if not math.isfinite(val):
            continue
        ts = datetime.strptime(row[0], "%Y-%m-%d %H:%M")
        if newest is None or ts > newest:
            newest = ts
    return newest  # station CSV clock; +8h = UTC


def coop_newest(text):
    # IEM daily.py pre-posts recent date rows with value None until data
    # arrives - only rows with an actual value count.
    newest = None
    for row in _data_rows(text):
        if row[0].lower() == 'station':
            continue
        try:
            val = row[2].strip()
            if val in ('', 'None', 'M'):
                continue
            if not math.isfinite(float(val)):
                continue
            d = datetime.strptime(row[1].strip(), "%Y-%m-%d")
        except (ValueError, IndexError):
            continue
        if newest is None or d > newest:
            newest = d
    return newest  # date; valid instant = 21:00 UTC that day


def log_one(index_fh, out_dir, station_key, url, parse_newest, to_utc, ext):
    rec = {"station": station_key, "url": url,
           "request_start_utc": datetime.now(timezone.utc)
           .isoformat(timespec="seconds")}
    try:
        raw = fetch(url)
    except Exception as err:  # noqa: BLE001 - failures are evidence
        rec["error"] = f"{type(err).__name__}: {err}"
        index_fh.write(json.dumps(rec) + "\n")
        index_fh.flush()
        print(f"{station_key}: FETCH FAILED {rec['error']}")
        return rec
    complete = datetime.now(timezone.utc)
    rec["response_complete_utc"] = complete.isoformat(timespec="seconds")
    rec["bytes"] = len(raw)
    rec["sha256"] = hashlib.sha256(raw).hexdigest()
    stamp = complete.strftime("%Y-%m-%dT%H%M%SZ")
    d = out_dir / station_key.replace(':', '-')
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{stamp}.{ext}"
    path.write_bytes(raw)  # raw bytes preserved before any parsing
    rec["raw_path"] = str(path)
    try:
        text = raw.decode("utf-8", errors="replace")
        newest_local = parse_newest(text)
        if newest_local is None:
            rec["newest_data"] = None
            rec["note"] = "no data rows in response"
        else:
            newest_utc = (newest_local.replace(tzinfo=timezone.utc)
                          + timedelta(hours=to_utc))
            rec["newest_data_utc"] = newest_utc.isoformat(timespec="seconds")
            lag = complete - newest_utc
            rec["availability_lag_hours_at_completion"] = round(
                lag.total_seconds() / 3600, 2)
    except Exception as err:  # noqa: BLE001 - parse failure must not lose
        rec["parse_error"] = f"{type(err).__name__}: {err}"  # other sources
        print(f"{station_key}: PARSE FAILED {rec['parse_error']} "
              f"(raw kept at {path})")
    index_fh.write(json.dumps(rec) + "\n")
    index_fh.flush()
    print(f"{station_key}: newest={rec.get('newest_data_utc')} "
          f"lag_h={rec.get('availability_lag_hours_at_completion')} "
          f"sha={rec['sha256'][:12]}")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="results/raw/obslog")
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / 'index.jsonl'
    with open(index_path, 'a', encoding='utf-8') as index_fh:
        for key, url, parser, to_utc, ext in build_requests(
                datetime.now(timezone.utc)):
            log_one(index_fh, out_dir, key, url, parser, to_utc, ext)
    print("index appended:", index_path)


if __name__ == "__main__":
    sys.exit(main())
