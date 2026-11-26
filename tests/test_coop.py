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
