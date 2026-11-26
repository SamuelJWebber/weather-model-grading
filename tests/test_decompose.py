from wxgrade.decompose import (classify_days, decomposition,
                               error_correlations, pearson)


ACT = {"2026-11-01": 0.10, "2026-11-02": 0.10, "2026-11-03": 0.15,
       "2026-11-04": 0.15, "2026-11-05": 0.14}


def test_classify_days_threshold():
    k = classify_days(ACT, 0.02)
    assert k == {"2026-11-02": "quiet", "2026-11-03": "change",
                 "2026-11-04": "quiet", "2026-11-05": "quiet"}
    assert "2026-11-01" not in k  # no prior day


def test_decomposition_paired_cells():
    series = {"m": {d: v + 0.01 for d, v in ACT.items()},
              "p": {d: ACT[d] for d in ACT}}  # p perfect
    out = decomposition(ACT, series, thresholds_m=(0.02,))
    cell = out["threshold_0.02"]
    assert cell["change"]["paired_days"] == 1
    assert cell["change"]["p"]["mae"] == 0.0
    assert cell["change"]["m"]["mae"] == 0.01
    assert cell["quiet"]["paired_days"] == 3


def test_pearson_and_correlations():
    assert pearson([1, 2, 3], [2, 4, 6]) == 1.0
    assert pearson([1, 2], [1, 2]) is None  # n<3
    assert pearson([1, 1, 1], [1, 2, 3]) is None  # zero variance
    # errors proportional -> r == 1.0; a perfect series has zero error
    # variance -> None (undefined, reported honestly)
    series = {"a": {d: v * 1.01 for d, v in ACT.items()},
              "b": {d: v * 1.02 for d, v in ACT.items()},
              "perfect": dict(ACT)}
    out = error_correlations(ACT, series)
    row = out["a vs b"]
    assert row["n"] == 5 and row["pearson"] == 1.0
    assert out["a vs perfect"]["pearson"] is None
