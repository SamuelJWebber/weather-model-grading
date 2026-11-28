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


def test_grade_reports_only_dates_shared_with_persistence():
    actual = {"2026-11-01": 1.0, "2026-11-02": 100.0,
              "2026-11-04": 70.0, "2026-11-05": 72.0}
    forecasts = {("model", 1): {"2026-11-04": 42.0, "2026-11-05": 71.0},
                 ("missing", 1): {}, ("no_prior", 1): {"2026-11-04": 70.0}}
    missing, model, no_prior = grade(forecasts, actual)
    assert model["forecast_n"] == 2 and model["n"] == 1
    assert model["paired_dates"] == ["2026-11-05"]
    assert model["mae"] == 1.0 and model["persistence_mae"] == 2.0
    assert missing["forecast_n"] == 0 and no_prior["forecast_n"] == 1
    for row in (missing, no_prior):
        assert row["n"] == 0 and row["paired_dates"] == []
        assert row["mae"] is None and row["persistence_mae"] is None


def test_replay_nyc_november_temperature_from_archived_responses(monkeypatch):
    import json
    from pathlib import Path
    from urllib.parse import parse_qs, urlsplit

    from wxgrade import grade as grading

    results = Path(__file__).resolve().parents[1] / "results"
    replay = json.loads((results / "raw/nyc-temperature/replay_2026-10-27_2026-11-25.json").read_text())
    old = json.loads((results / "grading_new-york-city_temperature_2026-11-25.json").read_text())
    combined = replay["previous_runs"]["hourly"]

    def cached(url):
        params = parse_qs(urlsplit(url).query)
        if "daily" in params:
            return replay["archive"]
        var, model = params["hourly"][0], params["models"][0]
        return {"hourly": {"time": combined["time"], var: combined[f"{var}_{model}"]}}

    monkeypatch.setattr(grading, "fetch_json", cached)
    forecasts = {(model, lead): grading.fetch_model_lead_max(40.71, -74.01, model, lead, 30)
                 for model in grading.MODELS for lead in grading.LEADS}
    actual = grading.fetch_actual_max(40.71, -74.01, *old["actual_window"])
    rows = grading.grade(forecasts, actual)
    assert len(rows) == len(old["rows"]) == 12
    for row, original in zip(rows, old["rows"]):
        assert (row["model"], row["lead_days"], row["mae"]) == (
            original["model"], original["lead_days"], original["mae"])
        assert row["n"] == row["forecast_n"] == 30
        assert row["paired_dates"] == sorted(forecasts[row["model"], row["lead_days"]])
        assert row["persistence_mae"] == {1: 4.567, 3: 7.427, 5: 8.900}[row["lead_days"]]
        unpaired = grading.score_series(grading.persistence_baseline(actual, row["lead_days"]), actual)
        assert unpaired["n"] == {1: 35, 3: 33, 5: 31}[row["lead_days"]]
        assert unpaired["mae"] == original["persistence_mae"]
