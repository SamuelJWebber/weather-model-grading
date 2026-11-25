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
