"""Saved station actuals with offline replay (independent audit finding W4).

Every grading artifact should be reproducible from saved inputs. Station
actuals (NRCS SNWD, IEM COOP) are pulled once per (source, window) and
saved under results/raw/actuals/ with fetch provenance; replay mode reads
only the saved file, so a re-run cannot silently drift when the upstream
revises its data (NRCS CSVs carry a 'subject to revision' warning).
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


def actuals_path(output_dir: str | Path, kind: str, key: str,
                 start: str, end: str) -> Path:
    safe = key.replace(":", "-").replace("/", "_")
    return (Path(output_dir) / "raw" / "actuals"
            / f"{kind}_{safe}_{start}_{end}.json")


def load_actuals(kind: str, key: str, start: str, end: str,
                 fetcher: Callable[[], dict[str, float]],
                 output_dir: str | Path = "results",
                 allow_fetch: bool = True) -> tuple[dict[str, float], dict]:
    """Return (values, meta). Reads the saved file when present; otherwise
    fetches and saves it. allow_fetch=False = offline replay (raises if
    the saved file is missing)."""
    path = actuals_path(output_dir, kind, key, start, end)
    def evidence(payload):
        csv_path = path.with_suffix('.csv')
        if not csv_path.exists():
            with csv_path.open('w', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(['date', 'snow_depth_m'])
                writer.writerows(sorted(payload['values'].items()))
        return {"path": str(path), "csv_path": str(csv_path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
                "source": payload.get("source", f"{kind}:{key}"),
                "fetched_utc": payload.get("fetched_utc"),
                "window": payload.get("window")}
    if path.exists():
        payload = json.loads(path.read_text())
        return ({k: float(v) for k, v in payload["values"].items()},
                {**evidence(payload), "saved": True})
    if not allow_fetch:
        raise FileNotFoundError(f"replay requested but no saved actuals: {path}")
    values = fetcher()
    meta = {"kind": kind, "key": key, "window": [start, end],
            "fetched_utc": datetime.now(timezone.utc).isoformat()}
    payload = {**meta, "values": values}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    meta.update({**evidence(payload), "saved": False})
    return values, meta
