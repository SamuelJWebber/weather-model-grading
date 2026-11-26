"""Offline fixture tests for wxgrade.contracts."""

from wxgrade.contracts import (coop_contract_verdict, parse_obhistory_snow,
                               parse_nrcs_hourly_midnight)


def test_coop_verdict_holds_once_daily_at_21():
    payload = {"data": [{"SDIRZZZ": 7.0, "utc_valid": "2026-11-15T21:00Z"},
                        {"tmpf": 20.0, "utc_valid": "2026-11-15T21:00Z"}]}
    reports = parse_obhistory_snow(payload)
    assert reports == [{"value_in": 7.0, "utc_valid": "2026-11-15T21:00Z"}]
    v = coop_contract_verdict(reports)
    assert v["contract_holds"] and v["reports_once_daily"]


def test_coop_verdict_fails_on_second_report_or_wrong_hour():
    two = [{"value_in": 7.0, "utc_valid": "2026-11-15T21:00Z"},
           {"value_in": 7.0, "utc_valid": "2026-11-15T22:00Z"}]
    assert not coop_contract_verdict(two)["contract_holds"]
    wrong = [{"value_in": 7.0, "utc_valid": "2026-11-15T07:00Z"}]
    assert not coop_contract_verdict(wrong)["contract_holds"]


def test_snotel_daily_equals_hourly_midnight():
    daily = "# header\n2026-11-24,4\n2026-11-25,4\n"
    hourly = "# header\n2026-11-25 00:00,4\n2026-11-25 01:00,4\n"
    out = parse_nrcs_hourly_midnight(daily, hourly, "2026-11-25")
    assert out["matches"] and out["daily_value"] == "4"
    hourly_bad = "# header\n2026-11-25 00:00,3\n"
    assert not parse_nrcs_hourly_midnight(daily, hourly_bad,
                                          "2026-11-25")["matches"]
