#!/usr/bin/env python3
"""Characterize the ECMWF snow_depth suspect series from the cached Single
Runs payloads (offline scan) plus three preserved live verification pulls.

Questions:
1. Per station/model, how many cached runs are all-zero snow_depth?
2. Does ECMWF depth stay exactly 0.0 while the SAME run's snowfall is
   nonzero? (live verify pulls, preserved under
   results/raw/singleruns/verify_*_ecmwf_depth_snowfall.json)

Findings (2026-11-26) are written up in
docs/ecmwf-snow-depth-characterization.md. Re-run: python3
scripts/ecmwf_depth_accumulation_check.py  (cache scan only, offline)
"""
import glob
import json
from pathlib import Path

CACHE = Path("results/raw/singleruns")
STATIONS = {"44.5248_-72.8154": "Stowe", "39.4800_-106.0700": "Breck",
            "39.6400_-106.3700": "Copper"}
MODELS = ("gfs_seamless", "icon_seamless", "ecmwf_ifs025")


def scan():
    for coords, label in STATIONS.items():
        print(f"== {label} {coords}")
        for model in MODELS:
            runs = allzero = 0
            nonzero = []
            for f in sorted(CACHE.glob(f"{coords}_{model}_*.json")):
                d = json.load(open(f))
                vals = [d[t] for t in sorted(d)]
                runs += 1
                nz = sum(1 for v in vals if v != 0.0)
                if nz == 0:
                    allzero += 1
                else:
                    nonzero.append((f.name[-15:-5], nz, round(max(vals), 3)))
            print(f"  {model:14s} runs={runs} all-zero={allzero} "
                  f"last-nonzero={nonzero[-2:]}")


def verify():
    for f in sorted(CACHE.glob("verify_*_ecmwf_depth_snowfall.json")):
        d = json.load(open(f))
        h = d["hourly"]
        sd, sf = h["snow_depth"], h["snowfall"]
        print(f"{f.name}: depth>0 {sum(1 for v in sd if v)}/48, "
              f"snowfall>0 {sum(1 for v in sf if v)}/48, "
              f"snowfall sum {sum(v for v in sf if v):.1f} cm")


if __name__ == "__main__":
    scan()
    print("== live-verify payloads (pulled 2026-11-26, preserved)")
    verify()
