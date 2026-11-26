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
