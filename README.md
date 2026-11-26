# weather-model-grading

Grades weather forecast models on real archived forecasts against actuals, so
"which model do I trust this week" has a numeric answer instead of folklore.

## Method

Verified mechanics (2026-11-24): forecasts use `temperature_2m_previous_dayN`
= the run issued N days before the target date (genuine lead-N), hourly values
reduced to daily max; both calls use timezone America/New_York and Fahrenheit,
and scoring joins on identical dates (n=30 per cell).

- Forecasts: Open-Meteo Previous Runs API, hourly `temperature_2m_previous_dayN`
  per model = the forecast a run issued N days earlier actually made. Genuine
  archived lead-N forecasts, not reanalysis.
- Actuals: Open-Meteo Historical Weather (Archive) API daily max temperature.
  Verified against the docs 2026-11-24: this is a REANALYSIS blend, not station
  observations - "based on reanalysis datasets" combining "weather station,
  aircraft, buoy, radar, and satellite observations", with gaps filled by
  mathematical models; the default Best Match mixes ECMWF IFS (9 km), ERA5
  (0.25 deg) and ERA5-Land (0.1 deg) seamlessly. Two consequences: grid-cell
  analysis is not a city thermometer, and the verification data itself contains
  ECMWF IFS, so ecmwf_ifs025 scores can be flattered by self-verification.
  Treat its second place as weaker evidence than the ICON/GFS gap. Both sources
  are Open-Meteo (CC BY 4.0 data).
- Metrics per model x lead (1/3/5 days): MAE, RMSE, bias, plus a persistence
  baseline (today's weather = N-days-ago actual) as the no-skill floor.

## First result (NYC, daily max temp, 30 days ending 2026-11-23)

| model | lead | MAE (F) | persistence MAE |
|---|---|---|---|
| icon_seamless | 1d | 1.55 | 4.15 |
| icon_seamless | 3d | 2.06 | 6.52 |
| icon_seamless | 5d | 2.62 | 7.77 |
| gfs_seamless | 1d | 1.95 | 4.15 |
| ecmwf_ifs025 | 1d | 2.14 | 4.15 |
| ukmo_seamless | 1d | 3.55 | 4.15 |

ICON led at every lead in this window; all four models beat persistence by a
wide margin. One location, one variable, one month: a sample ranking for this
place and season, not a general model winner.

## Station cross-check (added 2026-11-24)

The same 30-day window re-verified against a physical station thermometer:
hourly METAR observations for KNYC Central Park via the Iowa State IEM ASOS
service (free, no key), reduced to daily maxima. 29 overlapping days.

| model | lead | MAE vs station (F) | bias |
|---|---|---|---|
| icon_seamless | 1d | 1.17 | +0.08 |
| icon_seamless | 3d | 1.99 | -0.09 |
| icon_seamless | 5d | 2.61 | +0.11 |
| gfs_seamless | 1d | 1.57 | -0.41 |
| ecmwf_ifs025 | 1d | 1.87 | -1.08 |
| ukmo_seamless | 1d | 2.68 | -2.39 |

The ICON lead holds against station observations with near-zero bias, and the
reanalysis-era worry is confirmed in reverse: ECMWF's apparent second place
against the ECMWF-containing archive disappears against the station (GFS beats
it at 1 day). UKMO is worst on both verification bases. Still one station, one month, one variable: a sample

## Eastern actuals: Mount Mansfield COOP via IEM (integrated 2026-11-25, wxgrade/coop.py)

SNOTEL has no Northeast coverage; the verified eastern alternative is the
NWS COOP station MMNV1 "MT. MANSFIELD" (VT_COOP, on Stowe's own mountain),
served by the Iowa State IEM daily service (free, no key). Measurement
contract verified against raw reports, not assumed: the station is
automated (SHEF/DCP) and files snow depth exactly once daily at 21:00 UTC
(api/1/obhistory.json: SDIRZZZ 7.0in at 2026-11-15T21:00Z, 5.0in at
2026-11-18T21:00Z, matching the daily values). Forecast series are sampled
at that exact instant. Elevation: stake 1202m, Open-Meteo grid cell at the
station coordinate 1199m - a ~3m gap, a near-zero-gap head-to-head like
Vail. Coverage is patchy (26 of 30 days had values; missing days are
skipped and n is reported).

Controlled-lead result (Stowe / Mt Mansfield, valid instant 21:00 UTC,
00:00 UTC inits, leads 21h/45h, snow depth in meters). Actual window
2026-10-26..2026-11-24 (30 days, all valid times in the past at pull
time; window end is "yesterday" by construction, so no future actuals,
backfill or substituted years enter). The IEM feed itself is null on
2026-11-19, 11-20, 11-22 and 11-24; those days are skipped, giving
n=26 (persistence baseline n=23, it needs a prior present day).

| series | lead | MAE (m) | bias (m) |
|---|---|---|---|
| persistence (yesterday's depth) | baseline | 0.010 | -0.006 |
| gfs_seamless | 21h | 0.028 | -0.027 |
| gfs_seamless | 45h | 0.024 | -0.022 |
| icon_seamless | 21h | 0.030 | -0.030 |
| icon_seamless | 45h | 0.030 | -0.030 |
| ecmwf_ifs025 | 21h | 0.033 | -0.033 |
| ecmwf_ifs025 | 45h | 0.033 | -0.033 |

Reading: same pattern as Vail's quiet window - no model separates from
persistence, small uniform negative biases. On elevation: no LARGE
nominal gap is evident (stake 1202m, model grid cell at the stake
coordinate 1199m), unlike the western mountain diagnostics where the
grid sits 470-676m below the stake (audit 2026-11-25 corrected an
earlier "~1000m" here; the documented gaps are 470-676m). Close nominal elevation does not by
itself rule out elevation-related or other representativeness
confounding: a single stake on a wind-exposed ridgeline samples drift
and scour that a grid-cell mean does not, so quiet-weather depth drift,
stake exposure, grid smoothing or local elevation effects are all still
candidates for the -2..-3cm bias, and one station with 2 storm days
cannot separate them.
Storm subset n=2: too few to read; scored automatically every run.

Paired same-day check (2026-11-25, wxgrade/coop.py:paired_leads_check,
results/grading_stowe_snow-depth-coop-leads-paired_2026-11-24.json):
the table above scores each series on its own available dates (n=26
models vs n=23 persistence), which is not a paired comparison. The
check scores every series on the 23 dates where ALL series AND the
actual have values (2026-10-27..2026-11-18). It first re-derives the
window's inputs and reproduces every series' unrestricted scores
exactly (n/MAE/RMSE/bias all match the preserved artifact), then
reports paired scores at 4 decimals. Paired on the same 23 days:
persistence MAE 0.0099m; gfs_seamless 0.0264 (21h) / 0.0216 (45h);
icon_seamless 0.0285 / 0.0281; ecmwf_ifs025 0.0320 / 0.0320. The
unpaired conclusion stands on identical dates: no model beats
persistence in this quiet window (best model MAE 2.2x persistence),
model ranking unchanged (gfs < icon < ecmwf), biases still -2..-3cm.
Note: the check's first live run had a cache-key bug (runs cached by
init only, shared across models) that made all model series identical;
caught because per-model identity checks failed and fixed by keying the
cache on (model, init). The preserved artifact was never affected (its
loop caches per model).

Construction note (2026-11-24): both sides are maxima of hourly values, hourly model forecasts on one side and hourly METAR observations on the other, over New York local calendar days (both requests specify America/New_York); coverage was verified complete, 24-25 obs/day, zero missing hours. An hourly sampled high can still miss the true peak between observations, so small MAE differences between models are noise. KNYC sits ~7 km from the queried grid point. A sample
ranking, not a general model winner.

    PYTHONPATH=. python -m wxgrade.stations --live --station NYC --past-days 30
    PYTHONPATH=. python -m wxgrade.grade --live --location vail --variable snowfall --past-days 30

## First mountain run (Vail, 30 days ending 2026-11-23, America/Denver local days)

STATUS: implementation test of the generalized pipeline (location, timezone,
variable plumbing), not a verified snow-skill ranking. Independent mountain
actuals (a real snow-stake source) remain an open research item; until one is
verified, treat every number below as a plumbing check against grid-cell
archive analysis.

## Independent mountain actuals (SNOTEL, integrated 2026-11-24, wxgrade/snotel.py)

USDA NRCS SNOTEL site 842 "Vail Mountain" (physical snow pillow on the
mountain), free keyless CSV endpoint, verified live. Coverage correction:
SNOTEL covers the 11 western US states + Alaska ONLY - Stowe VT has NO
SNOTEL station (NWS COOP on Mount Mansfield is the eastern alternative,
not yet integrated); Whistler (BC) and Zermatt (CH) need their national
networks, unverified.

Verified stations (each checked 2026-11-25 against the NRCS site page
and a live SNWD pull; pillow elevation vs Open-Meteo model grid-cell
elevation at the resort coordinate):

| resort | SNOTEL station | pillow elev | grid elev | gap | dist |
|---|---|---|---|---|---|
| vail | 842:CO:SNTL Vail Mountain (on-mountain) | 2495m | 2495m | ~0 | ~0 |
| breckenridge | 531:CO:SNTL Hoosier Pass | 3536m | 3066m | 470m | ~13km |
| park_city | 814:UT:SNTL Thaynes Canyon | 2822m | 2146m | 676m | ~4km |
| palisades | 784:CA:SNTL Palisades Tahoe | 2441m | 1916m | 525m | ~3km |

Breckenridge note: the nearest SNOTEL by distance is Copper Mountain
(415, ~9km) but that pillow sits on a different resort's terrain, so
Hoosier Pass was chosen instead.

Matched-variable discipline: SNOTEL measures snow DEPTH (SNWD,
start-of-day inches). It is NOT a snowfall observation, and SNWD deltas
are net of settling/compaction - so snowfall forecasts are never scored
against SNOTEL. Scoring uses Open-Meteo's snow_depth variable on both
sides, start-of-day values, meters.

Measurement contract (verified 2026-11-25, not assumed):
- Daily SNWD is an INSTANT, not a day summary: the CSV header reads
  "Snow Depth (in) Start of Day Values" and daily[D] == hourly[D 00:00]
  (checked at 842 for 2026-11-24).
- Station reporting time is fixed-offset local standard time, no DST,
  and the offset is per-station, not per-state: all four stations above
  report at UTC-8 (opensnotel.com station records, utcOffsetMinutes=-480
  for all four, corroborated by a latest-hourly-timestamp check at
  ~08:00 UTC 2026-11-25 showing every station's latest stamp at 23:00
  the prior day). So daily SNWD[D] = depth at 08:00 UTC of date D, and
  the forecast series is sampled at that exact instant (fixed Etc/GMT+8,
  never the resort's IANA zone). Guarded by a test.
- Units: inches -> meters (x0.0254) on the actual side; Open-Meteo
  hourly snow_depth is meters.

Lead provenance, resolved 2026-11-25: the Previous Runs API retains no
snow_depth (verified all-null 2026-11-24), but the Single Runs API
serves snow_depth with non-null, run-resolved values for
gfs_seamless/icon_seamless/ecmwf_ifs025 (same valid instant, different
runs give different values), with the run's UTC initialisation time
explicit in the request - exact issue/lead provenance. Archive reach
was measured 2026-11-25 (results/singleruns_availability_2026-11-25.json):
the Single Runs API serves runs from 2026-04-02 onward for ALL probed
models including ecmwf_ifs025 - the docs statement that ECMWF IFS HRES
runs are archived from 2024-03 does NOT hold on this endpoint (every
2024-03..2026-01 probe returned HTTP 400 'run not available'). So
controlled lead-N snow-depth grading is possible from this season
onward only (run_snotel_leads_live); past winters are unreachable on
this route, and the storm-day sample grows only from new accumulation.
The Historical Forecast API reaches past winters but with mixed/unknown
lead provenance, which breaks this measurement contract.

Controlled-lead result (Vail, valid instant = station midnight 08:00
UTC, runs initialised at 00:00 UTC exactly 8h or 32h earlier, per-date
init/valid provenance in the results JSON; rolling window, n=33):

| series | lead | MAE (m) | bias (m) |
|---|---|---|---|
| persistence (yesterday's depth) | baseline | 0.010 | -0.003 |
| icon_seamless | 8h | 0.011 | -0.009 |
| icon_seamless | 32h | 0.013 | -0.007 |
| gfs_seamless | 8h | 0.014 | -0.014 |
| gfs_seamless | 32h | 0.014 | -0.009 |
| ecmwf_ifs025 | 8h | 0.018 | +0.005 |
| ecmwf_ifs025 | 32h | 0.016 | -0.001 |

Reading: no model separates from persistence and no 8h->32h degradation
in this window - but the window had few snow events and snow depth is
slow-moving, so this measures quiet-weather tracking, NOT storm skill.
The lead_8h column closely matches the recent_run series below, an
internal consistency check (recent_run is a short mixed lead). The
results JSON also scores a storm subset (dates with >=5cm start-of-day
depth rise vs the prior present day; SNWD deltas are net of settling,
so this undercounts events): the window contains exactly ONE such day
(2026-11-21), so storm skill is unmeasurable so far - the subset is
scored automatically on every run and becomes informative as winter
accumulation arrives.

First matched result (Vail, recent_run series - consecutive most-recent
runs, short mixed lead, no per-step issue time; n=35 days, snow depth
in meters, model grid cell vs on-mountain pillow - a real basis
difference; rolling window, so exact values shift by a day):

| series | lead | MAE (m) | bias (m) |
|---|---|---|---|
| persistence (yesterday's depth) | baseline | ~0.009 | ~-0.003 |
| icon_seamless | recent_run | ~0.011 | ~-0.009 |
| gfs_seamless | recent_run | ~0.014 | ~-0.014 |
| ecmwf_ifs025 | recent_run | ~0.016 | ~+0.005 |
| ukmo_seamless | recent_run | no data (all null) | - |

Reading: at this short mixed lead the models are at or slightly WORSE
than persistence - expected, since snow depth is slow-moving and the
window had few snow events; this says nothing yet about storm-day skill.

Station expansion results (2026-11-25, recent_run, n=35 days, meters;
same rolling-window caveat as Vail):

| resort | gfs | icon | ecmwf | persistence |
|---|---|---|---|---|
| breckenridge | 0.110 | 0.116 | 0.127 | 0.013 |
| park_city | 0.135 | 0.149 | 0.136 | 0.029 |
| palisades | 0.113 | 0.165 | 0.075 | 0.043 |

This table is a coverage/mismatch diagnostic, NOT a skill ranking.
Every model bias is negative and roughly equal to its MAE, and the bias
magnitude tracks the elevation gap in the station table above (Vail gap
~0 with models near persistence; 470-676m gaps with 8-18cm under-reads).
The elevation gap is a PLAUSIBLE CONFOUND consistent with this pattern,
not an established cause: four correlated sites cannot isolate it, and
other representativeness differences (station siting, distance, terrain,
model grid physics) remain in play. Nor is Vail a clean head-to-head:
a near-zero elevation gap is only one requirement, and the recent_run
series lacks verified issue-time/lead provenance (addressed for Vail
by the controlled-lead run above). No bias correction is applied or
justified on the current evaluation window. Consequence for the
project: before any model ranking from SNOTEL, verify the full
measurement contract (done above) and prefer elevation-matched
stations.

Elevation-matched test of that confound (2026-11-25, recent_run, n=35,
meters): one active SNOTEL station per resort chosen near the model
grid-cell elevation (verified via opensnotel records: active, daily
SNWD available, UTC-8 reporting; live NRCS pulls in the run):

| resort | matched station | gap | gfs | icon | ecmwf | persistence |
|---|---|---|---|---|---|---|
| breckenridge | 415:CO:SNTL Copper Mountain, 8.8km, 3200m | +134m | 0.015 | 0.009 | 0.009 | 0.007 |
| park_city | 1321:UT:SNTL Mill Creek Canyon, 15.0km, 2121m | -25m | 0.022 | 0.036 | 0.024 | 0.014 |
| palisades | 834:CA:SNTL Truckee #2, 12.2km, 1981m | +65m | 0.011 | 0.048 | 0.047 | 0.028 |

The 8-18cm negative biases collapse to ~1-5cm (both signs) when the
station sits near grid elevation, landing in the same range as
persistence - exactly what the elevation-gap confound predicts. Still
not proof of mechanism: the station, its siting, and its distance all
changed at once, and n=1 matched station per resort. But for any future
SNOTEL-based model comparison, elevation-matched stations are now the
demonstrated requirement, and the on-resort pillows above are retained
only as the mismatch diagnostic.

Controlled-lead runs at the matched stations (2026-11-25, lead 8h / 32h
MAE m, per-date run provenance in the results JSONs; Vail included as
the on-mountain matched case):

| station | gfs 8h/32h | icon 8h/32h | ecmwf 8h/32h | persistence | storm n |
|---|---|---|---|---|---|
| Vail Mountain | 0.014/0.014 | 0.011/0.013 | 0.018/0.016 | 0.010 | 1 |
| Copper Mountain (breck) | 0.016/0.014 | 0.010/0.011 | 0.009/0.009 | 0.008 | 2 |
| Mill Creek Canyon (park city) | 0.023/0.022 | 0.039/0.039 | 0.026/0.026 | 0.015 | 3 |
| Truckee #2 (palisades) | 0.013/0.022 | 0.052/0.054 | 0.038/0.037 | 0.030 | 4 |

Reading: at matched stations the models sit within ~2x of persistence
with no consistent cross-station ranking and no consistent 8h->32h
degradation - still a quiet-weather window (1-4 storm days per site),
so these are tracking measurements, not skill claims. Storm subsets are
scored per run and become informative as accumulation arrives.

Daily max temp, vs archive actuals (MAE F):

| model | lead 1 | lead 3 | lead 5 |
|---|---|---|---|
| ecmwf_ifs025 | 1.21 | 1.85 | 2.32 |
| ukmo_seamless | 1.35 | 1.91 | 2.97 |
| gfs_seamless | 1.59 | 2.05 | 3.09 |
| icon_seamless | 1.62 | 2.07 | 2.96 |

All four beat persistence (~5.5 F MAE) by a wide margin. ECMWF leads here,
unlike NYC, but it verifies against an ECMWF-containing archive (self-verification
caveat from the method section applies directly).

Daily snowfall sum (cm), vs archive actuals:

| model | lead 1 | lead 3 | lead 5 |
|---|---|---|---|
| icon_seamless | 0.07 | 0.13 | 0.16 |
| ukmo_seamless | 0.18 | 0.24 | 0.24 |
| gfs_seamless | 0.20 | 0.24 | 0.45 |
| ecmwf_ifs025 | no data | no data | no data |

ecmwf_ifs025 exposes no snowfall_previous_dayN series in the Previous Runs API
(response valid, all nulls), so it is excluded from snowfall grading.

Snowfall caveat: the 36-day actual window (Oct 19 - Nov 23) had only 6
nonzero snowfall days totaling 6.0 cm, so these MAEs are dominated by correct
zero forecasts. This ranking is event-thin and says little about storm-day
skill yet; the pipeline is what was built today, and the numbers will get
meaningful as winter accumulates events. Grid-cell archive analysis is not a
mountain snow stake either.

## Usage

    PYTHONPATH=. python -m wxgrade.grade --live --lat 40.71 --lon -74.01 --past-days 30
    PYTHONPATH=. python -m pytest tests/   # offline

Live pulls are manual only; tests never touch the network.
