# Observation-log pilot handoff (2026-11-26)

## Purpose (narrow)

Measure **source availability latency** for the snow-depth actuals used by
weather-model-grading, so a future operational (issue-time) comparison can
say what a forecaster could have seen at forecast issue time. This pilot
does NOT itself perform operational validation, and it does not resolve
every open validation question (ECMWF suspect depth series, storm-day
skill, and any model-ranking question are out of scope).

## What exists now

- `scripts/observe_now.py` (attached): standalone collector, python3 stdlib
  only, no repo checkout or keys needed. Per run it fetches 5 sources,
  records request start AND response completion separately
  (`request_start_utc` / `response_complete_utc`; availability lag is
  measured from completion, when the bytes actually arrived), preserves
  each raw response (`results/raw/obslog/<station>/<fetch_stamp>.csv` +
  sha256) BEFORE parsing, parses the newest data instant, and appends +
  flushes one JSONL row per source to `results/raw/obslog/index.jsonl`
  the moment that source finishes. A fetch failure is logged as a row
  with `error` set; a parse failure is logged with `parse_error` set and
  the raw bytes already on disk - neither can lose or block evidence for
  the other sources.
- First snapshots already preserved in-repo: 2026-11-26 19:56/19:57/19:58
  UTC (pre-fix schema, `fetch_utc` = request start), including one
  transient fetch failure and one parser-fix pair. A fourth run at ~20:03
  UTC with the corrected collector logged 403s on all four SNOTEL fetches
  while the COOP fetch succeeded - see Rate limiting below.

## Sources (actual URLs in use)

- SNOTEL hourly snow depth (4 stations: 842:CO:SNTL Vail Mountain,
  415:CO:SNTL Copper Mountain, 1321:UT:SNTL Mill Creek Canyon,
  834:CA:SNTL Truckee #2):
  `https://wcc.sc.egov.usda.gov/reportGenerator/view_csv/customSingleStationReport/hourly/<triplet>%7Cid=%22%22%7Cname/<start>,<end>/SNWD::value`
  (script requests a rolling 3-day window; free, no key)
- COOP daily snow depth (MMNV1 Mt. Mansfield VT):
  `https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py?network=VT_COOP&stations=MMNV1&sts=<start>&ets=<tomorrow>&var=snowd_in`
  (rolling 7-day window; free, no key). `ets` is an inclusive end DATE
  per the service docs
  (https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py?help=);
  the collector requests tomorrow's date so nothing already filed can be
  censored by the window - a future end date is harmless (only existing
  rows are returned). An earlier version ended the window at today
  00:00Z, which could have censored same-day filings; a regression test
  (`tests/test_observe_now.py`) now pins the window coverage.

Timestamp conventions: the SNOTEL hourly CSV carries no timezone. NRCS
AWDB documentation states SNOTEL (SNTL network) hourly measurements are
recorded in Pacific Standard Time (UTC-8, year-round), except "a few
stations in Alaska and elsewhere" in station local time
(https://opencdss.state.co.us/tstool/latest/doc-user/datastore-ref/NRCS-AWDB/NRCS-AWDB/,
mirroring NRCS AWDB docs). None of these four stations is in Alaska, and
the +8h conversion is additionally anchored per station in-repo: hourly
row "D 00:00" equals daily SNWD[D] (33/33 match within 0.5in,
`scripts/hourly_persistence_snotel_check.py`). Doc plus empirical anchor
together; neither alone. COOP `snowd_in[D]` = depth at D 21:00 UTC
(measurement contract). IEM daily.py pre-posts recent dates with value
`None` until data arrives; the parser skips value-less rows and rejects
non-finite numerics.

## Proposed 14-day pilot

- Window: 2026-11-27 .. 2026-12-10 (14 days).
- Cadence: every 3 hours (8 runs/day). Each run: 5 GETs, ~3s total,
  ~50-250 KB raw stored. 14 days ~ 10-30 MB.
- Corrected cadence rationale: hourly values CAN appear at each hourly
  fetch, and a 3h cadence does NOT capture when each row first became
  available - it brackets first-availability to 3h precision. Because a
  3h-wide bracket can straddle the 3h-delay cutoff itself, a pilot
  outcome at any station can be SUPPORTED (observed lag strictly under
  the cutoff across the sample), CONTRADICTED (strictly over), or
  INDETERMINATE (brackets straddle the cutoff) - supportability is a
  possible outcome, not a guaranteed one. (The delayed-anchor sensitivity
  in `results/hourly_persistence_snotel_2026-11-26.json` used init-3h as
  its most optimistic case.) If 1h-precision availability is ever needed,
  the cadence must be hourly; that is a separate, larger collection
  decision.
- Rate limiting (observed): at ~20:03 UTC on 2026-11-26, after several
  rapid successive pulls during development, all four SNOTEL fetches
  returned HTTP 403 while the COOP fetch succeeded (rows preserved in
  `index.jsonl`). The 3h cadence is far below any plausible threshold,
  but an hourly cadence should be adopted only with backoff/retry
  handling and an explicit rate check.
- End-of-pilot analysis: per-station availability-lag distribution
  (response_complete_utc - newest data instant), revision incidence (see
  below), COOP gap pattern; then a decision on whether an operational
  same-lead comparison is supportable at SNOTEL stations, with
  indeterminate as an explicit possible verdict.

## Retention and revision properties (clarified)

- Each snapshot requests a rolling window (3 days SNOTEL, 7 days COOP),
  so older values are retained across many overlapping snapshots. If a
  source REVISES a past value, earlier raw snapshots preserve the
  original bytes and later ones show the revision - revisions are
  detectable by diffing snapshots, with sha256 per file. Deletions
  (a value row disappearing) are equally visible.
- Forecast side: archived model runs re-pulled after issue were
  value-identical in TWO samples (Fairbanks ECMWF 00Z run re-pulled 5h
  later; Vail GFS 2026-11-13T00:00 init re-pulled 13 days later, 48/48
  hourly values identical). This is sampled evidence consistent with
  immutable archived runs, NOT a verified no-revision policy: init
  provenance alone does not prove issue-time contents. If issue-time
  forecast contents ever need proof, the collector would have to snapshot
  forecasts at issue time too (out of this pilot's scope).
- Note: the repo's `results/raw/singleruns/` cache holds PARSED
  {time: value} series, not raw API payloads; the obslog preserves raw
  bytes.

## Execution instructions

1. Copy `observe_now.py` anywhere with python3 (stdlib only).
2. Run: `python3 observe_now.py` from a working directory; it creates
   `results/raw/obslog/` under the CWD. (In the repo, run from the repo
   root so snapshots land with the grading data.)
3. For the pilot, schedule 8 runs/day (e.g. cron `17 */3 * * *` -
   minute offset arbitrary) for 2026-11-27..2026-12-10, then stop.
4. Analysis: read `results/raw/obslog/index.jsonl`; group by station;
   availability lag is the `availability_lag_hours` column.

## Limitations (stated, not resolved by the pilot)

- Sampled availability at these public endpoints is not identical to
  what any specific forecaster tooling would see; it is the verifiable
  public-source bound.
- One-day sampling so far shows ~1h SNOTEL hourly availability and a
  ~71h COOP lag with 11-24/11-25 values absent entirely; the pilot
  exists because one sample is not a distribution.
- An earlier ">38h hourly lag" claim (from window-censored pulls) is
  RETRACTED; see README's latency paragraph. This retraction is
  load-bearing for the pilot's motivation and is preserved in the repo
  README and artifacts.
- The pilot measures availability only. It does not establish storm-day
  skill, does not clear or further indict the suspect ECMWF depth
  series at Copper/Stowe, and does not validate any selector.
