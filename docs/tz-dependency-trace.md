# Dependency trace: provisional SNOTEL hourly timezone (2026-11-26)

Trigger: the SNOTEL hourly CSV clock->UTC +8h conversion is PROVISIONAL
(NRCS AWDB docs say PST for the SNTL network except "a few stations in
Alaska and elsewhere"; the in-repo 33/33 daily anchor verifies only
date-boundary assignment at whole-hour granularity). This trace lists
which existing outputs depend on sub-daily timing of SNOTEL hourly
values and therefore inherit the caveat. Offline inspection only.

## AFFECTED (depend on the sub-daily +8h conversion)

1. `results/hourly_persistence_snotel_2026-11-26.json` - same-lead
   hourly-persistence benchmark at 4 SNOTEL stations (8h/32h leads),
   including the Truckee GFS-beats-persistence exception numbers and the
   delayed-anchor sensitivity (init-3h/-24h/-48h). Anchor instants are
   computed with the conversion (per-station whole-hour offset selected
   by the daily anchor, scripts/hourly_persistence_snotel_check.py:160).
   A whole-hours offset error would shift every anchor and could move
   borderline pairings. Flag field `timezone_provisional_2026-11-26`
   added to the artifact and embedded in the script so regeneration
   retains it.
2. `results/hourly_persistence_vail_2026-11-26.json` - the earlier
   single-station (Vail 842) version of the same check
   (scripts/hourly_persistence_check.py:101, fixed +8h). Same flag added
   to artifact and script.
3. `results/raw/obslog/index.jsonl` - `newest_data_utc` and
   `availability_lag_hours*` on the four snotel rows per round use the
   conversion (scripts/observe_now.py). Raw rows are preserved evidence
   and were not rewritten; the collector docstring and the pilot handoff
   (`docs/obslog-pilot-handoff.md`, Open blockers #2) state that all lag
   numbers inherit the provisional-timezone caveat.

## UNAFFECTED (grounded)

- All daily paired grading results (storm-day MAE, paired same-day
  comparisons, decomposition, ECMWF exclusion supplement): actuals are
  daily SNWD values with explicit dates from the daily report route
  (wxgrade/snotel.py), no sub-daily conversion. The 33/33 anchor
  verifies exactly this date-level correspondence.
- NYC + Vail temperature grading refresh (9e61c15, bedd520): actuals
  from the Open-Meteo Archive API (wxgrade/grade.py:6,25), not SNOTEL.
- COOP/MMNV1 results: the 21:00 UTC measurement contract is a separate
  convention, not derived from the SNOTEL conversion.
- ECMWF snow-depth characterization
  (docs/ecmwf-snow-depth-characterization.md): open-meteo forecast
  payloads only, no SNOTEL hourly timing.
- Fed language watch and Citi Bike projects: no SNOTEL data at all.

## User-facing exposure

None requires correction: no user-facing deliverable (File, message, or
published repo) contains SNOTEL hourly-timing claims. The only delivered
File is the Citi Bike study (unrelated). Weather results live only in
the unpublished local repo; README and artifacts now carry the caveat at
the points listed above.

## Resolution path (unchanged, deferred)

AWDB StationMetaData.stationDataTimeZone per station triplet (field
documented in the official AWDB Web Service User Guide). Deferred: it is
an NRCS endpoint, gated on the same access-guidance blocker as the
obslog pilot.
