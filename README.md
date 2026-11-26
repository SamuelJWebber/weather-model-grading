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

## First result (NYC, daily max temp; refreshed 2026-11-26, 30 days ending 2026-11-25)

| model | lead | MAE (F) | persistence MAE |
|---|---|---|---|
| icon_seamless | 1d | 1.70 | 4.60 |
| icon_seamless | 3d | 2.09 | 7.14 |
| icon_seamless | 5d | 2.54 | 8.91 |
| gfs_seamless | 1d | 2.11 | 4.60 |
| ecmwf_ifs025 | 1d | 2.14 | 4.60 |
| ukmo_seamless | 1d | 3.28 | 4.60 |

ICON led at every lead in this window; all four models beat persistence by a
wide margin. One location, one variable, one month: a sample ranking for this
place and season, not a general model winner. (First window, ending
2026-11-23: icon 1.55/2.06/2.62, gfs 1.95, ecmwf 2.14, ukmo 3.55 at the
same rows - same ranking, small drift. The NYC snowfall window is now
entirely zero: the early-November events rolled out of the rolling 30
days, so snowfall MAEs are all 0.0 and carry no information until the
next event. Artifacts: results/grading_new-york-city_*_2026-11-25.json.)

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
Leads are NOMINAL (init-to-valid): the archive records initialization, not the time a user could
first retrieve the forecast. Operational publication latency was not
measured here; usable lead is shorter and may vary by model:

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
| Copper Mountain (breck) | 0.016/0.014 | 0.010/0.011 | 0.009/0.009 (SUSPECT const-zero series) | 0.008 | 2 |
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
0.0118; Copper 0.0079 vs ecmwf 0.0095 (ecmwf = SUSPECT const-zero
series, see the ECMWF paragraph below; excluding it, best single is
icon 0.0101 and still loses); Mill Creek 0.0151 vs gfs
0.0227. The one case of a single model beating persistence SURVIVES
pairing: gfs at Truckee #2, 0.0133 (8h) and 0.0231 (32h) vs persistence
0.0302 - same quiet-window and single-station caveats apply, and icon
(0.0532) and ecmwf (0.0397) are both far worse than persistence there,
so it is one model at one station, not a pattern. (2026-11-26 audit
repair: ensemble_mean_3 rows added to every paired artifact. The
ensemble beats persistence overall at two of five stations - Vail
0.0067 vs 0.0095 at 8h, Truckee 0.0083 vs 0.0302 at 8h - and loses at
the other three: Copper 0.0111 vs 0.0079, Mill Creek 0.0293 vs 0.0151,
Stowe 0.0290 vs 0.0099 (Stowe and Copper ensembles include the SUSPECT
ECMWF const-zero depth series; excluding it, the 2-model ensembles are
0.0275/0.0249 at Stowe and 0.0125/0.0120 at Copper and still lose to
persistence - see the ECMWF paragraph and exclusion supplement below).
So persistence beats each single model except GFS at Truckee,
with a further 2/5-station ensemble exception - a
retrospective diagnostic from this quiet window, not a selector; any
ensemble use would need a prospective test. The Stowe pairing move is
larger than the SNOTEL ones: gfs 45h 0.0240 -> 0.0216. Checks now
replay fully offline from saved actuals + cached raw runs.)

Daily max temp, vs archive actuals (MAE F; refreshed 2026-11-26, 30 days
ending 2026-11-25; results/grading_vail-co-epic_temperature_2026-11-25.json):

| model | lead 1 | lead 3 | lead 5 |
|---|---|---|---|
| ecmwf_ifs025 | 1.16 | 1.73 | 2.24 |
| ukmo_seamless | 1.43 | 2.00 | 2.79 |
| gfs_seamless | 1.68 | 2.02 | 2.96 |
| icon_seamless | 1.62 | 1.95 | 2.80 |

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

## Audit-repaired retrospective decomposition (2026-11-26)

Corrections of record: (1) the first hourly-persistence numbers
mis-computed anchors (sub-day timedelta bug; superseded, notes in the
artifacts); (2) the ">38h hourly / <32h daily SNOTEL" latency claims
were confounded by window-censored pulls and are RETRACTED - direct
sampling (results/raw/obslog/, 2026-11-26 ~19:57 UTC) shows ~1h SNOTEL
hourly availability and a ~71h COOP MMNV1 lag. Details in the latency
and same-lead benchmark paragraphs below; pilot handoff in
docs/obslog-pilot-handoff.md.


Inputs: saved actuals JSON plus CSV, hashes, fetch timestamps and station
identifiers in results/raw/actuals/; cached forecasts in
results/raw/singleruns/. The saved actuals were first preserved during
this audit repair. They cannot prove what a prior unsaved fetch returned,
but all five paired checks reproduce their preserved unrestricted scores.
allow_fetch=False now disables network reads for both actuals and missing
forecast cache entries. Automated artifact replay verifies n/MAE/RMSE/bias
for every paired artifact with network fetchers forbidden.

The decomposition now includes start-1 actuals. An observed-linear
extrapolation supplement needs two previous actuals and is kept on a
separate intersection so it no longer drops the first day from the main
scores. Model-delta-persistence means yesterday's observed depth plus
the model's change between consecutive valid-day forecasts. This is
separate from observed linear extrapolation, and its smaller available
sample is explicitly reported. Every paired artifact includes both
model-delta-persistence and zero-depth supplements.

Main short-lead overall paired scores, meters (not a forward test):

| station | n | persistence | ensemble mean | best single model |
|---|---:|---:|---:|---|
| vail | 32 | 0.0095 | 0.0067 | icon_seamless: 0.0118 |
| breckenridge | 32 | 0.0079 | 0.0111 | ecmwf_ifs025: 0.0095 (SUSPECT const-zero series; excl. ECMWF: icon_seamless 0.0101, still loses to persistence) |
| park_city | 32 | 0.0151 | 0.0293 | gfs_seamless: 0.0238 |
| palisades | 32 | 0.0302 | 0.0083 | gfs_seamless: 0.0133 |
| stowe | 24 | 0.0095 | 0.0278 | gfs_seamless: 0.0253 |

The ensemble beats persistence at Vail and Truckee, and loses at the
other three stations. GFS alone beats persistence at Truckee. These are
retrospective exceptions, not an actionable selector. Correlations do
not establish benefit: the actual ensemble error is computed above.
Bias offsetting by an outlier model can explain cancellation without
showing a dependable ensemble advantage on future data.

ECMWF is exactly zero in all cached hourly runs at Copper and Stowe,
including before confirmed snow days. (Label map: "Copper" = the
breckenridge resort grid cell 39.48,-106.07 verified against SNOTEL
415:CO:SNTL Copper Mountain station, 8.8km away, +134m gap - not the
Copper Mountain resort grid; "Stowe" = COOP station MMNV1 Mt. Mansfield
at its own coordinates 44.5248,-72.8154, valid 21:00 UTC.) Its constant-zero tie is exposed
in the saved baselines. Resolution (2026-11-26 PM,
results/ecmwf_zero_resolution_2026-11-26.json): live Single Runs
discriminators show the same run's snowfall is nonzero on inits where
snow_depth stayed exactly 0.0 (Stowe 11-13: 17/47h nonzero snowfall;
Copper 11-20: 9/47h), and the variable works at a snow-covered control
cell (Fairbanks, 0.14m). The depth series at these two cells is
therefore SUSPECT - it cannot be read as a model forecast of zero
depth. Root cause is UNRESOLVED (a vendor-side serving gap is one
hypothesis; ECMWF-side processing or grid/elevation masking are not
excluded), and the reliability of ECMWF snowfall at these cells is
itself unverified. Consequence: every ECMWF snow_depth score at Copper
and Stowe in this document measures the suspect series; the exclusion is
a methodological sensitivity choice (an uninterpretable series should
not drive rankings), not a determination that ECMWF depth is generally
unusable. Observed behavior and open alternative explanations:
docs/ecmwf-snow-depth-characterization.md.
results/ecmwf_exclusion_supplement_2026-11-26.json (identity-verified
offline replay) recomputes the affected paired conclusions without
ECMWF: no headline flips (persistence still beats every model and both
ensemble variants at both cells), but the breckenridge "best single
model" cell below is icon_seamless 0.0101 once the suspect series is
excluded, not ecmwf_ifs025 0.0095.

The original forward definitions remain 0.01/0.02/0.03 meters. For
integer-inch observations these select >=1in, >=1in, and >=2in. The first
two are duplicates, retained only to preserve original frozen definitions.
Persistence error equals the realized absolute depth change by
construction, so realized change/quiet splits are nearly tautological
and cannot select a forecast before the outcome. Hourly station 842
values flicker by one inch; event cells at that scale may be sensor noise.

Separately labeled supplementary cells report MAE in inches and realized
>=2in / >=3in counts, plus a forecast-predicted-change split using GFS
versus yesterday's actual. These supplements were defined after seeing
this sample. Prior-day actual reporting latency, directly sampled
2026-11-26 ~19:57 UTC via scripts/observe_now.py (results/raw/obslog/,
retrieval timestamps + raw responses preserved): SNOTEL hourly values
were available ~1h after the observation instant at all four stations;
COOP MMNV1's newest value was ~71h old (11-24 and 11-25 absent
entirely; IEM pre-posts recent dates with None values until data
arrives). Earlier window-bounded latency claims here (>38h hourly,
<32h daily SNOTEL) were confounded by requested windows and are
retracted; the COOP 11-24 absence was and is real. Consequence split
by source: SNOTEL hourly actuals look operationally available (~1h
sampled lag, one sample), so a same-lead operational comparison at
SNOTEL stations is FEASIBLE going forward via the obslog; COOP actuals
are not (multi-day gaps), so any Stowe forecast-based split remains a
candidate selector, not a validated operational rule. Inch threshold comparisons use a tiny float
roundoff tolerance; original frozen centimeter comparisons are unchanged.
The artifact, not a prose significance claim, contains the full cells.

Separate post-audit sensitivity now lives in scripts/audit_sensitivity.py
and results/audit_sensitivity_2026-11-26.json. It includes Spearman,
IID-day bootstrap intervals (serial dependence ignored, descriptive only),
a one-inch deadband and trailing-three-day-median targets. Original
thresholds and artifacts remain separate. No same-lead hourly
persistence benchmark exists yet. Nominal lead is not measured operational lead.
Original historical artifacts remain historical evidence, not retroactive
claims of saved inputs or an operational forecast-skill ranking.


Sensitivity on identical dates across targets: Vail n=30 ensemble versus
persistence MAE in inches is raw 0.28/0.40, deadband 0.32/0.23, trailing
median 0.37/0.20. Truckee n=30 is raw 0.35/1.27, deadband 0.36/1.17,
trailing median 1.19/1.03. Thus the raw ensemble advantage reverses for
Vail under both alternate targets and Truckee under the median target.
These targets differ from raw depth and do not identify sensor truth.
The result limits any claim of a stable advantage; it is not evidence
that one transformed target should replace the original target.

Same-lead hourly persistence benchmark (2026-11-26 PM;
results/hourly_persistence_vail_2026-11-26.json and
results/hourly_persistence_snotel_2026-11-26.json): hourly SNWD pulled
from NRCS for all four matched SNOTEL stations (raw CSVs + sha256
preserved; each station's timestamp convention verified 33/33 against
its saved daily series, "D 00:00" = D 08:00 UTC). Stowe excluded:
COOP MMNV1 reports daily only. Scored gfs/icon at leads 8h/32h against
persistence anchored lead-hours before the SAME valid instant.
"Same-lead" makes the anchor coincide with the init instant at every
lead (anchor = valid - lead = init), so the anchor observation could
NOT have been available at issue time - an observation is not
transmitted before it exists. (Direct availability sampling on
2026-11-26 ~19:57 UTC, results/raw/obslog/: SNOTEL hourly values were
available ~1h after the observation instant at all four stations; an
earlier ">38h lag" statement here was confounded by the pull's
requested window and is retracted.) The benchmark is therefore
retrospective and symmetric (same
horizon as the model); it uses observations unavailable at issue and
is not an operational selector. It is NOT an upper bound on
operational persistence skill: a more recent anchor does not guarantee
smaller realized error, and a delayed anchor can do better on some
samples. Hourly station values flicker ~1 inch.
(Correction: the first version of this check mis-computed anchors via
date-minus-timedelta hour arithmetic - the 8h anchor landed after the
valid instant and the 32h anchor 24h before it; numbers here are the
corrected ones and the artifacts carry the correction note.)

Hourly-persistence vs model MAE (m), paired common dates:

| station | n | lead | hourly pers | daily pers | gfs | icon | models beat hourly pers? |
|---|---|---|---|---|---|---|---|
| Vail 842 | 30 | 8h/32h | 0.0059/0.0119 | 0.0098 | 0.0153/0.0149 | 0.0126/0.0126 | no |
| Copper 415 (breck) | 31 | 8h/32h | 0.0025/0.0074 | 0.0082 | 0.0172/0.0153 | 0.0104/0.0113 | no |
| Mill Creek 1321 (park city) | 25 | 8h/32h | 0.0061/0.0183 | 0.0156 | 0.0304/0.0260 | 0.0508/0.0490 | no |
| Truckee 834 (palisades) | 31/30 | 8h/32h | 0.0139/0.0406 | 0.0311 | 0.0137/0.0247 | 0.0549/0.0591 | GFS at 8h: 0.0137 vs 0.0139 (difference 0.0002, no equality criterion defined); GFS at 32h: 0.0247 < 0.0406 |

Read (retrospective only): at Vail, Copper and Mill Creek, gfs and
icon lose to same-lead zero-lag hourly persistence in this window.
That comparison grants the benchmark information unavailable at issue
time, so it does NOT establish that models lose to any operational
persistence - it is one retrospective contrast, not a conservative
form of an operational claim. At Truckee, GFS is below hourly
persistence at 32h (0.0247 vs 0.0406) and 0.0002 below it at 8h
(0.0137 vs 0.0139) - consistent with its paired daily-persistence
exception. Quiet window, one model at one station: not a pattern.

Delayed-anchor sensitivity (same artifact; anchor at init-3h/-24h/-48h,
each on its own maximal date intersection; operational timeliness is
ASSUMED, not established - though the obslog's ~1h sampled SNOTEL
availability makes the 3h delay plausible, one sample only): persistence stays ahead of both models at Copper at
nearly every delay (exception: icon edges the 3h-delayed anchor at
32h, 0.0118 vs 0.0141). At Mill Creek, GFS drops below the 24-48h
delayed anchors (0.0283 vs 0.0349 at 8h/48h). At Truckee, GFS is
below the delayed anchors at every delay and lead (e.g. 8h/24h:
0.0141 vs 0.0406) and icon joins at 24-48h delays. So the
operational-direction comparison differs by station: persistence
robust at Copper, GFS increasingly competitive at Mill Creek, GFS
clearly ahead at Truckee. Small n, quiet window, descriptive only.

Label map: "Vail" = resort grid 39.64,-106.37 vs on-mountain SNOTEL
842:CO:SNTL (gap ~0); Copper/Mill Creek/Truckee per the
elevation-matched station table above.
