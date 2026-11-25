"""Offline tests for ASOS station parsing and comparison."""

from wxgrade.stations import compare_forecasts_to_station, parse_asos_csv

CSV = """station,valid,tmpf
NYC,2026-11-20 00:51,51.00
NYC,2026-11-20 12:51,63.00
NYC,2026-11-20 23:51,55.00
NYC,2026-11-21 06:51,M
NYC,2026-11-21 13:51,58.20
"""


def test_parse_asos_csv_daily_max_and_missing():
    out = parse_asos_csv(CSV)
    assert out["2026-11-20"] == 63.0
    assert out["2026-11-21"] == 58.2
    assert len(out) == 2


def test_compare_forecasts_to_station():
    forecasts = {("modelA", 1): {"2026-11-20": 62.0}}
    rows = compare_forecasts_to_station(forecasts, parse_asos_csv(CSV))
    assert rows[0]["n"] == 1 and rows[0]["mae"] == 1.0
    assert rows[0]["bias"] == -1.0


def test_snotel_parse():
    from wxgrade.snotel import parse_snwd_csv, INCHES_TO_M
    from pathlib import Path
    text = Path(__file__).parent.joinpath("fixtures/snotel_842.csv").read_text()
    d = parse_snwd_csv(text)
    assert d == {"2026-11-17": 0.0, "2026-11-18": 1.0, "2026-11-19": 0.0,
                 "2026-11-21": 3.0, "2026-11-22": 4.0}
    assert abs(3 * INCHES_TO_M - 0.0762) < 1e-9
