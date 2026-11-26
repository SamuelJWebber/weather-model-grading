# ECMWF snow_depth suspect series - behavioral characterization (2026-11-26)

Status: the suspect-series question is now characterized at the API-behavior
level; the vendor-level mechanism (which GRIB field / conversion inside
open-meteo or ECMWF IFS open data produces this) remains unexplained
upstream. This note narrows, and corrects the scope of, the earlier
"suspect series" finding.

## What the cache scan shows (scripts/ecmwf_depth_accumulation_check.py)

All-zero snow_depth runs in the cached Single Runs payloads
(results/raw/singleruns/), per station and model:

| Station | GFS | ICON | ECMWF |
| --- | --- | --- | --- |
| Stowe (44.5248,-72.8154) | 23/31 | 24/31 | 31/31 |
| Breck (39.4800,-106.0700) | 13/34 | 15/34 | 34/34 |
| Copper (39.6400,-106.3700) | 20/34 | 16/34 | 30/34 |

The zero pattern is not scattered: ECMWF runs are zero for EVERY hour of
the run, never a leading-block or partial pattern (0 partial runs
anywhere). GFS and ICON at the same coordinates produce accumulating,
plausible values in the majority of runs.

## Live verification pulls (preserved: results/raw/singleruns/verify_*)

Pulled 2026-11-26 from the Single Runs API (run=<init>T00:00,
forecast_hours=48, hourly=snow_depth,snowfall):

- Stowe init 2026-11-13: depth>0 in 0/48 h; snowfall>0 in 17/48 h, 6.9 cm total.
- Stowe init 2026-11-15: depth>0 in 0/48 h; snowfall>0 in 12/48 h, 0.8 cm total.
- Breck init 2026-11-21: depth>0 in 0/48 h; snowfall>0 in 15/48 h, 4.2 cm total.

So ECMWF snow_depth via this API stays exactly 0.0 while the same run
predicts accumulating snowfall.

## When ECMWF depth is nonzero

Only Copper inits from 2026-11-21 onward (the day snow reached the
ground in the analysis) return nonzero depth, decaying slowly
(0.20 -> 0.17 m over 11-21..11-24). ECMWF depth therefore behaves as a
reflection of analyzed snow cover, not as a forecast that accumulates
predicted snowfall - at these three locations, on this API, over this
cached window (2026-10-22..11-24).

## Consequences

1. This explains the earlier breck "best single model" artifact: a flat
   0.0 series scores an excellent RMSE whenever actuals are near zero
   (the pre-storm window). The exclusion supplement already re-scored
   breck to icon; this note records WHY the ECMWF number looked good.
2. Any snow-depth grading that includes ECMWF snow_depth from the Single
   Runs API is comparing a non-accumulating field against accumulating
   ones; the comparison is not like-for-like. ECMWF depth should stay
   excluded (or be relabeled "analyzed-cover echo") until the mechanism
   is resolved upstream.
3. Temperature-based ECMWF results are unaffected by this note.

## What remains open

- Vendor-level mechanism: whether open-meteo zero-fills a missing IFS
  open-data field, derives depth from snow water equivalent with missing
  density, or IFS open data itself omits forecast snow-depth
  accumulation. The open-meteo issue tracker has no exact-match issue
  (searched 2026-11-26; the closest, #1827, is a different symptom on a
  different API: era5_seamless gap-filling plus a 33.33 m glacier cap on
  the Archive API).
- Whether the behavior is location-independent (sample here: 3 mountain
  coordinates; Fairbanks control previously shown working, so not
  universal).
- ECMWF's own documentation of `sd` in IFS open-data forecast steps was
  not located in this pass.
