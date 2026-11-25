"""Offline tests for wxgrade scoring functions."""

from __future__ import annotations

from wxgrade.grade import grade, persistence_baseline, score_series


def test_score_series_basic():
    pred = {"2026-11-01": 60.0, "2026-11-02": 62.0, "2026-11-03": 55.0}
    act = {"2026-11-01": 61.0, "2026-11-02": 60.0, "2026-11-03": 57.0, "2026-11-04": 50.0}
    out = score_series(pred, act)
    assert out["n"] == 3
    assert out["mae"] == 1.667
    assert abs(out["rmse"] - 3 ** 0.5) < 1e-3
    assert out["bias"] == -0.333


def test_score_series_empty_overlap():
    assert score_series({"2026-01-01": 1.0}, {"2026-01-02": 1.0})["n"] == 0


def test_persistence_baseline_shifts_by_lead():
    act = {f"2026-11-0{d}": float(d) for d in range(1, 7)}
    base = persistence_baseline(act, 2)
    assert base["2026-11-04"] == act["2026-11-02"]
    assert "2026-11-01" not in base


def test_grade_includes_persistence_and_sorts():
    forecasts = {
        ("modelA", 1): {"2026-11-02": 10.0, "2026-11-03": 10.0},
        ("modelB", 1): {"2026-11-02": 0.0, "2026-11-03": 0.0},
    }
    act = {"2026-11-01": 8.0, "2026-11-02": 9.0, "2026-11-03": 11.0}
    rows = grade(forecasts, act, leads=(1,))
    assert [r["model"] for r in rows] == ["modelA", "modelB"]
    a = rows[0]
    assert a["n"] == 2 and a["mae"] == 1.0
    # persistence for lead 1: predict previous day's actual
    assert abs(a["persistence_mae"] - 1.5) < 1e-9


def test_fetch_model_lead_daily_sum_reduce(monkeypatch):
    from wxgrade import grade

    payload = {
        "hourly": {
            "time": ["2026-11-20T00:00", "2026-11-20T01:00", "2026-11-21T00:00"],
            "snowfall_previous_day1": [0.5, 1.0, 2.0],
        }
    }
    monkeypatch.setattr(grade, "fetch_json", lambda url: payload)
    out = grade.fetch_model_lead_daily(39.64, -106.37, "icon_seamless", 1, 3,
                                       variable="snowfall", reduce="sum")
    assert out == {"2026-11-20": 1.5, "2026-11-21": 2.0}
