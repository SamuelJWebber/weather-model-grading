import json

import pytest

from wxgrade.actuals import actuals_path, load_actuals


def test_fetch_then_replay(tmp_path):
    calls = []

    def fetcher():
        calls.append(1)
        return {"2026-11-01": 0.1}

    vals, meta = load_actuals("snotel", "842:CO:SNTL", "2026-11-01",
                              "2026-11-01", fetcher, output_dir=tmp_path)
    assert vals == {"2026-11-01": 0.1} and meta["saved"] is False
    vals2, meta2 = load_actuals("snotel", "842:CO:SNTL", "2026-11-01",
                                "2026-11-01", fetcher, output_dir=tmp_path,
                                allow_fetch=False)
    assert vals2 == vals and meta2["saved"] is True
    assert len(calls) == 1  # second read came from disk


def test_replay_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_actuals("coop", "MMNV1", "2026-11-01", "2026-11-02",
                     lambda: {}, output_dir=tmp_path, allow_fetch=False)


def test_all_saved_paired_artifacts_replay_without_network(monkeypatch):
    from pathlib import Path
    from wxgrade import snotel, coop
    import math
    def forbidden(*args, **kwargs):
        raise AssertionError('network not permitted in replay')
    monkeypatch.setattr(snotel, 'fetch_singlerun_hourly', forbidden)
    monkeypatch.setattr(snotel, 'fetch_snwd_daily', forbidden)
    monkeypatch.setattr(coop, 'fetch_snowd_daily', forbidden)
    for r in ['vail', 'breckenridge', 'park_city', 'palisades', 'stowe']:
        files = list(Path('results').glob(f'grading_{r}_*paired*2026-11-24.json'))
        assert len(files) == 1
        expected = json.loads(files[0].read_text())
        original_bytes = files[0].read_bytes()
        try:
            if r == 'stowe':
                got = coop.paired_leads_check(allow_fetch=False)
            else:
                got = snotel.paired_snotel_leads_check(
                    r, station=snotel.ELEVATION_MATCHED_STATIONS.get(r), allow_fetch=False)
            assert got['common_dates'] == expected['common_dates']
            assert got['paired_scores'] == expected['paired_scores']
            assert all(v['matches'] for v in got['identity_check_vs_preserved_artifact'].values())
        finally:
            files[0].write_bytes(original_bytes)


def test_offline_missing_forecast_never_fetches(tmp_path, monkeypatch):
    from wxgrade import snotel
    monkeypatch.setattr(snotel, 'fetch_singlerun_hourly', lambda *a: (_ for _ in ()).throw(AssertionError('network')))
    with pytest.raises(FileNotFoundError):
        snotel._singlerun_cached(1, 2, 'gfs', '2026-11-01', tmp_path, allow_fetch=False)


def test_empty_cache_is_rejected_offline(tmp_path):
    from wxgrade.snotel import _singlerun_cached
    (tmp_path / '1.0000_2.0000_gfs_2026-11-01.json').write_text('{}')
    with pytest.raises(FileNotFoundError):
        _singlerun_cached(1, 2, 'gfs', '2026-11-01', tmp_path, allow_fetch=False)
