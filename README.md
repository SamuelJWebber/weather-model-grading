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

Controlled lead-N snow-depth grading is an UNRESOLVED research problem:
the Previous Runs API retains no snow_depth (snow_depth_previous_dayN
verified all-null for all four models, 2026-11-24). Accumulating
current-run forecasts daily is one verified route to controlled leads;
other archive sources have not been ruled out. What runs today is the
Historical Forecast API - consecutive most-recent model runs, a short
mixed lead (~0-24h), labeled recent_run, never "lead-1".

First matched result (Vail, n=32 days, snow depth in meters, model grid
cell vs on-mountain pillow - a real basis difference; rolling window, so
exact values shift by a day):

| series | lead | MAE (m) | bias (m) |
|---|---|---|---|
| persistence (yesterday's depth) | baseline | ~0.009 | ~-0.002 |
| icon_seamless | recent_run | ~0.010 | ~-0.008 |
| gfs_seamless | recent_run | ~0.012 | ~-0.012 |
| ecmwf_ifs025 | recent_run | ~0.016 | ~+0.003 |
| ukmo_seamless | recent_run | no data (all null) | - |

Reading: at this short mixed lead the models are at or slightly WORSE
than persistence - expected, since snow depth is slow-moving and the
window had few snow events; this says nothing yet about storm-day skill.
The interesting test is controlled lead-N accumulation.

Station expansion results (2026-11-25, recent_run, n=32 days, meters;
same rolling-window caveat as Vail):

| resort | gfs | icon | ecmwf | persistence |
|---|---|---|---|---|
| breckenridge | 0.116 | 0.123 | 0.135 | 0.013 |
| park_city | 0.148 | 0.163 | 0.149 | 0.032 |
| palisades | 0.124 | 0.180 | 0.082 | 0.047 |

The dominant signal here is NOT forecast skill: every model bias is
negative and roughly equal to its MAE, and the bias size tracks the
elevation gap in the station table (Vail gap ~0, models match
persistence; 470-676m gaps, models under-read depth by 8-18cm).
Model grid cells sit below the pillows, so the cells hold less snow.
At mismatched elevations, raw model-vs-pillow snow-depth scoring mostly
measures the grid-elevation difference, not forecast error. Consequence
for the project: SNOTEL scoring needs elevation-matched stations (or an
explicit bias correction by elevation gap) before model rankings mean
anything. Vail remains the only clean head-to-head so far.

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
