from wxgrade.decompose import classify_days, model_delta_persistence, supplementary_cells


def test_exact_two_inches_survives_float_roundoff_only_in_supplement():
    actual = {'2026-11-01': 11 * .0254, '2026-11-02': 13 * .0254}
    out = supplementary_cells(actual, {'gfs_seamless': actual})
    assert out['inch_thresholds']['2in']['change_day_count'] == 1


def test_model_delta_uses_model_change_and_prior_actual():
    a = {'2026-11-01': .2, '2026-11-02': .3}
    m = {'2026-11-01': .1, '2026-11-02': .14}
    assert abs(model_delta_persistence(a, m)['2026-11-02'] - .24) < 1e-12
