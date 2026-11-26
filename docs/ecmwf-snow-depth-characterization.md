# ECMWF snow_depth suspect series - observed behavior (2026-11-26)

Status: descriptive observations of the cached Single Runs payloads and
three live verification pulls. Interpretations are listed as open
alternatives, not conclusions.

## Observed (scripts/ecmwf_depth_accumulation_check.py)

All-zero snow_depth runs in the cached Single Runs payloads
(results/raw/singleruns/), per station and model:

| Station | GFS | ICON | ECMWF |
| --- | --- | --- | --- |
| Stowe (44.5248,-72.8154) | 23/31 | 24/31 | 31/31 |
| Breck (39.4800,-106.0700) | 13/34 | 15/34 | 34/34 |
| Copper (39.6400,-106.3700) | 20/34 | 16/34 | 30/34 |

- ECMWF zeros are whole-run: every hour of the run is exactly 0.0, never
  a partial or leading-block pattern, in every cached ECMWF run at Stowe
  and Breck and 30/34 at Copper (window 2026-10-22..11-24).
- GFS and ICON at the same coordinates return nonzero values in a
  majority of runs. NOTE: models differ in terrain representation, grid
  cell and land mask at identical query coordinates, so this contrast
  does NOT isolate a model-specific cause; a location/grid effect
  interacting with each model's terrain remains possible.
- Live verify pulls (preserved: results/raw/singleruns/verify_*): at
  Stowe inits 2026-11-13 / 11-15 and Breck init 2026-11-21, ECMWF
  snow_depth is exactly 0.0 for all 48 hours while the same run's
  snowfall totals 0.8-6.9 cm.
- ECMWF depth is nonzero only in Copper inits from 2026-11-21 onward,
  the day snow reached the ground at that station; values decline
  0.20 -> 0.17 m over 11-21..11-24.

## Open alternative explanations (not discriminated by this sample)

- The API field reflects analyzed snow cover with limited or no forecast
  accumulation for these cells.
- Forecast snowfall melts or compacts to zero depth in the model's snow
  scheme at these grid cells (warm/seasonal ground, elevation mismatch
  between model grid cell and station).
- Variable definition mismatch: the queried snow_depth field may not be
  the accumulating snow-cover field for this model/API combination
  (e.g., derived from snow water equivalent with missing density).
- Grid-cell/terrain/land-mask effects that differ per model at the same
  query coordinates (the GFS/ICON contrast does not rule this out).
- Vendor- or converter-level gap (missing GRIB field, zero-fill).
  The open-meteo issue tracker has no exact-match issue (searched
  2026-11-26; #1827 is a different API and symptom).

## Bounded consequences

1. Arithmetic note on the earlier breck "best single model" cell: a
   flat-zero prediction series produces a small RMSE whenever actuals
   are near zero, as they were in the pre-storm window. This explains
   the small number arithmetically; it says nothing about the upstream
   cause of the zeros.
2. ECMWF snow_depth stays excluded from depth grading as a
   METHODOLOGICAL SENSITIVITY CHOICE (a series we cannot yet interpret
   should not drive rankings), already reflected in the exclusion
   supplement. Whether all ECMWF depth on this API is unsuitable is NOT
   established here; the sample is three mountain coordinates over five
   weeks, and a Fairbanks control previously returned plausible values.
3. Temperature-based ECMWF results are a separate matter: this note is
   about the snow_depth variable only and neither validates nor
   invalidates the temperature comparisons.

## What would discriminate

Station-metadata elevation vs model-cell elevation comparisons,
snow-cover-specific variables (e.g., SWE, snow density) from the same
runs, ECMWF's own `sd` field documentation for IFS open-data forecast
steps (not located 2026-11-26), or an upstream answer from open-meteo.
No further fetches are planned without new evidence.
