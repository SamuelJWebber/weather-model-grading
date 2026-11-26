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
unpaired conclusion stands on identical dates: no SINGLE model beats
persistence in this quiet window (best model MAE 2.2x persistence),
model ranking unchanged (gfs < icon < ecmwf), biases still -2..-3cm.
(2026-11-26 audit repair: ensemble_mean_3 rows added - 0.0290 at 21h /
0.0272 at 45h, also far worse than persistence 0.0099 here; and the
check now replays fully offline from saved actuals + cached raw runs.)
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
  (verified with saved raw CSVs at ALL FOUR stations: 842 for
  2026-11-24/25, 415 + 1321 + 834 for 2026-11-25,
  results/contracts/snotel_*).
- Station reporting time is fixed-offset local standard time, no DST,
  and the offset is per-station, not per-state: all four stations above
  report at UTC-8. Strongest evidence is the raw CSVs' own "As of:"
  footer, parsed by wxgrade/contracts.py:parse_nrcs_asof_offset -
  GMT-08:00 in every saved daily and hourly file at all four stations
  (a lag-based timestamp heuristic could not discriminate UTC-8 from
  UTC-7; the footer can). Corroborated by opensnotel.com station
  records (utcOffsetMinutes=-480) and a latest-hourly-timestamp check. So daily SNWD[D] = depth at 08:00 UTC of date D, and
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
init/valid provenance in the results JSON; rolling window, n=33).
Leads are NOMINAL (init-to-valid): the 00:00 UTC run's output posts
~4-5h later for GFS and ~7-8h later for ECMWF, so the decision-useful
lead at the 08:00 UTC valid instant is ~3-4h for GFS and ~0-1h for
ECMWF, not 8h:

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

Paired same-day check (2026-11-26, wxgrade/snotel.py:
paired_snotel_leads_check, results/*-paired_*.json): the table above
scores models on n=33 days vs persistence on n=32 (unpaired). The
check re-derives each window's inputs (raw Single Runs payloads cached
under results/raw/singleruns/ as evidence), verifies every series'
unrestricted scores reproduce the preserved artifacts exactly, then
scores all series on the 32 common dates (2026-10-24..2026-11-24) at 4
decimals. At the SNOTEL stations pairing moves MAEs by <=0.0013 and
changes no ranking: Vail persistence 0.0095 vs best SINGLE model icon
0.0118; Copper 0.0079 vs ecmwf 0.0095; Mill Creek 0.0151 vs gfs
0.0227. The one case of a single model beating persistence SURVIVES
pairing: gfs at Truckee #2, 0.0133 (8h) and 0.0231 (32h) vs persistence
0.0302 - same quiet-window and single-station caveats apply, and icon
(0.0532) and ecmwf (0.0397) are both far worse than persistence there,
so it is one model at one station, not a pattern. (2026-11-26 audit
repair: ensemble_mean_3 rows added to every paired artifact. The
ensemble beats persistence overall at two of five stations - Vail
0.0067 vs 0.0095 at 8h, Truckee 0.0083 vs 0.0302 at 8h - and loses at
the other three: Copper 0.0111 vs 0.0079, Mill Creek 0.0293 vs 0.0151,
Stowe 0.0290 vs 0.0099. So "persistence wins overall" holds for single
models everywhere, with a 2/5-station ensemble exception - a
retrospective diagnostic from this quiet window, not a selector; any
ensemble use would need a prospective test. The Stowe pairing move is
larger than the SNOTEL ones: gfs 45h 0.0240 -> 0.0216. Checks now
replay fully offline from saved actuals + cached raw runs.)

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

## Error decomposition: quiet days vs change days (2026-11-26, wxgrade/decompose.py)

The paired checks above score whole windows; this asks WHERE persistence's
edge comes from, using the cached raw runs (results/raw/singleruns/) plus
one actuals pull per station (results/decomposition_2026-11-26.json;
short-lead series: 8h SNOTEL / 21h COOP). Descriptive, small n.

2026-11-26 audit-repair state: station actuals are now SAVED next to the
artifact (results/raw/actuals/*.json, fetch provenance inside) and the
whole decomposition replays offline from cache + saved actuals
(verified: replay output identical to live); actuals are fetched from
one day BEFORE the window so the persistence baseline is defined on the
first window day (an earlier version silently dropped that day from the
baseline, n=31 vs the models' 32); two extra baselines are scored on
every artifact - delta-persistence (linear extrapolation of the last
observed change) and constant-zero-depth - and an overall same-date
paired score row exists for EVERY series including the ensemble.

0. **Overall paired scores (n=31 per station except Stowe n=23).** No
   SINGLE model beats persistence anywhere: Vail 0.0098 vs best single
   icon 0.0122; Copper 0.0082 vs ecmwf 0.0098; Mill Creek 0.0156 vs gfs
   0.0245; Truckee 0.0311 vs gfs 0.0137 - the one single-model exception,
   already in the paired section; Stowe 0.0099 vs gfs 0.0264. The
   3-model ENSEMBLE beats persistence overall at 2 of 5 stations (Vail
   0.0069 vs 0.0098; Truckee 0.0086 vs 0.0311) and loses at three
   (Copper 0.0114 vs 0.0082; Mill Creek 0.0302 vs 0.0156; Stowe 0.0290
   vs 0.0099) - retrospective, and it works exactly where member errors
   disagree (item 4). Delta-persistence never beats plain persistence;
   constant-zero-depth is far worse everywhere except where the model
   itself is a zero predictor (next item).
1. **Some "models" are zero-depth predictors at these grid cells.** The
   const_zero_depth baseline ties ecmwf EXACTLY at Copper (both 0.0098)
   and Stowe (both 0.0320): ECMWF's snow_depth is literally zero for
   every cached run at those cells, including the init issued ahead of
   the confirmed +3in storm day at Copper and the +4in/+3in days at
   Stowe (evidence: results/ecmwf_zero_check_2026-11-26.json - 0 of 34
   Copper and 0 of 31 Stowe cached ECMWF payloads have any nonzero hour,
   vs 21/34 and 8/31 for gfs). Real model behavior or vendor gap is
   indistinguishable from the data; scored honestly as a zero predictor,
   and the ensemble_mean_3 inherits that drag at those cells.
2. **Quiet days stack the deck for persistence.** On days where the
   start-of-day depth is unchanged from the prior day, persistence's
   error is zero BY CONSTRUCTION (it predicts yesterday's depth; its
   change/quiet split is near-tautological since its error is |delta
   actual|), while models carry 0.3-0.9cm of noise. Most days in these
   windows are quiet (19-24 of ~31 paired days per station), so the
   whole-window "no single model beats persistence" is substantially
   this composition effect.
3. **On change days the picture flips at some stations.** At a >=1in
   (2.54cm) day-over-day depth change (SNWD is integer inches, so the
   frozen 1cm and 2cm thresholds select the SAME days; the frozen 3cm
   threshold is really >=2in), paired MAE on change days: Vail n=10
   persistence 0.0305 best among singles (ensemble 0.0144 beats all);
   Copper Mountain n=7 ALL THREE models beat persistence (gfs 0.0154 /
   icon 0.0155 / ecmwf 0.0327 vs 0.0363); Mill Creek n=7 persistence
   0.0689 best; Truckee n=12 gfs 0.0297 beats persistence 0.0804
   (icon/ecmwf worse, ensemble 0.0157 best); Stowe n=4 delta-persistence
   0.0381 and persistence 0.0571 both beat every model.
4. **On the biggest days (realized >=2in change, 12 station-days total)
   gfs beats persistence at ALL FIVE stations** (Vail n=1 1.82in vs
   3.0in; Copper n=2 1.12 vs 2.5; Mill Creek n=2 4.58 vs 6.5; Truckee
   n=5 1.20 vs 6.0; Stowe n=2 2.74 vs 3.5). At >=3in (9 station-days)
   the same direction holds (Truckee n=3 1.31 vs 8.67). Consistent
   direction but 9-12 station-days: a pattern to test as real storms
   arrive, NOT a finding.
5. **Model errors are often the same errors - and where they are not,
   the actual ensemble score improves.** Per-day signed-error
   correlations between model pairs reach 0.90-0.996 at Park City and
   Stowe, but are NEGATIVE for some pairs at Vail (ecmwf/icon -0.773)
   and Palisades (ecmwf/icon -0.835). The actual same-date 3-model
   mean (no new forecast pulls) confirms the mechanism both ways on
   change days: at Vail it scores 0.0144 (beats every member AND
   persistence 0.0305) and at Truckee 0.0157 (beats persistence 0.0804
   and best member gfs 0.0297), while at Park City (0.134) and Stowe
   (0.123) it loses to persistence (0.0689 / 0.0571), exactly where
   correlations are high. Correlation alone did not establish this;
   the computed scores did - but both are RETROSPECTIVE diagnostics on
   n=4-12 change days, not a selector. Any ensemble use would be a
   prospective decision tested forward, not adopted from this table.

SUPPLEMENTARY (separately labeled; frozen definitions above unchanged):
ex-ante stratification by FORECAST-predicted change (|gfs prediction -
yesterday's observed depth| >= 1in, known before the day) - at Vail the
ensemble scores 0.66in MAE on 10 predicted-change days vs persistence
0.91in; at Truckee 0.92in vs 3.88in; at Mill Creek persistence wins
predicted-change days 2.71in vs ensemble 5.27in. This split is a usable
selector in principle, unlike the realized-change strata, but it is
fitted on the same 31 days and would need a prospective test. Event
reporting in inches at >=2in (>=3in preferred) is in the artifact's
supplementary_inch_exante block; the 1in sensor-noise floor is real -
the station 842 hourly CSV flipped 3<->4in 17 times in 3 days
(results/contracts/snotel_842-CO-SNTL_*).

Caveats: one quiet November window; change-day counts are 4-12 per
station at >=1in and 1-5 at >=2in; depth deltas are net of
settling/compaction (the storm subset undercounts events); SNWD's
integer-inch quantization makes the frozen 1cm/2cm thresholds identical
and puts 1in at the sensor noise floor; the realized change/quiet strata
are retrospective diagnostics, not actionable selectors; the thresholds
and definitions are frozen for the forward test and will not be retuned
to future results; nothing here is a storm-skill claim. The forward test
is the next real storm window: predictions implied by this decomposition
are (a) persistence wins quiet days trivially, (b) gfs should beat
persistence on >=2in change days if the pattern is real.
