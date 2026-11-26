"""Offline tests for the IEM COOP daily parser and measurement contract."""

from pathlib import Path

from wxgrade.coop import (COOP_STATIONS, INCHES_TO_M, SAMPLE_UTC_HOUR,
                          parse_daily_csv)


def test_parse_daily_csv_fixture():
    text = Path(__file__).parent.joinpath(
        "fixtures/iem_mmnv1_daily.csv").read_text()
    d = parse_daily_csv(text)
    # Real pull 2026-11-25: 11-13 trace (0.0001in), 11-14..11-18 values,
    # 11-19 None and must be skipped (patchy coverage).
    assert d == {"2026-11-13": 0.0001, "2026-11-14": 4.0, "2026-11-15": 7.0,
                 "2026-11-16": 7.0, "2026-11-17": 6.0, "2026-11-18": 5.0}


def test_inches_to_m():
    assert abs(7.0 * INCHES_TO_M - 0.1778) < 1e-9


def test_contract_sample_hour():
    # Measurement contract (verified 2026-11-25 via obhistory SDIRZZZ):
    # daily snow depth is the 21:00 UTC report, so the forecast series is
    # sampled at 21:00 UTC, never at an IANA-zone local hour.
    assert SAMPLE_UTC_HOUR == 21
    for st in COOP_STATIONS.values():
        assert st["station"] == "MMNV1" and st["network"] == "VT_COOP"


def test_paired_intersection_logic(tmp_path, monkeypatch):
    """Paired check scores every series on the common dates only, and the
    identity check flags any mismatch with the preserved artifact."""
    import json
    from wxgrade import coop

    actual = {"2026-11-20": 0.10, "2026-11-21": 0.12, "2026-11-22": 0.15,
              "2026-11-23": 0.15}
    # 11-20 and 11-23 are missing for the model; 11-20 lacks a prior
    # actual for persistence -> common = {11-21, 11-22} only.
    monkeypatch.setattr(coop, "fetch_snowd_daily",
                        lambda *a, **k: dict(actual))
    # real fetch returns only non-None hourly values
    fake_run = {"2026-11-21T21:00": 0.13, "2026-11-22T21:00": 0.16}
    import wxgrade.snotel as snotel_mod
    monkeypatch.setattr(snotel_mod, "fetch_singlerun_hourly",
                        lambda *a, **k: dict(fake_run))
    ref = {"actual_window": ["2026-11-20", "2026-11-23"], "rows": []}
    ref_path = tmp_path / "ref.json"
    ref_path.write_text(json.dumps(ref))
    out = coop.paired_leads_check(
        leads_h=(21,), compare_to=str(tmp_path / "ref.json"),
        output_dir=str(tmp_path))
    assert out["common_dates"] == ["2026-11-21", "2026-11-22"]
    for name, s in out["paired_scores"].items():
        assert s["n"] == 2, name
    # persistence errors are 0.02 and 0.03 on the two common days
    p = out["paired_scores"]["persistence_1d baseline"]
    assert abs(p["mae"] - 0.025) < 1e-9
    # identity check records the empty artifact rows without matching
    assert all(not v["matches"] for v in
               out["identity_check_vs_preserved_artifact"].values())
