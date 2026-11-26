"""Offline regression tests for the observation-log sampler."""
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import observe_now as on


def _times():
    # Midday, near midnight, and year boundary - window edges are where
    # censoring bugs live.
    return [datetime(2026, 11, 26, 19, 58, tzinfo=timezone.utc),
            datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc),
            datetime(2027, 1, 1, 0, 1, tzinfo=timezone.utc)]


def test_coop_window_covers_now_and_then_some():
    """Regression: the earlier version ended the COOP window at today
    00:00Z, which could censor same-day data. The end date must be AFTER
    the fetch instant (IEM `ets` is an inclusive end date; a future date
    is harmless and guarantees nothing already filed is excluded)."""
    for now in _times():
        for key, url, parser, to_utc, ext in on.build_requests(now):
            if not key.startswith("coop"):
                continue
            q = parse_qs(urlparse(url).query)
            ets = datetime.strptime(q["ets"][0], "%Y-%m-%d").replace(
                tzinfo=timezone.utc)
            sts = datetime.strptime(q["sts"][0], "%Y-%m-%d").replace(
                tzinfo=timezone.utc)
            assert ets > now, "COOP window must end after the fetch time"
            assert sts < now


def test_snotel_window_covers_now():
    for now in _times():
        for key, url, parser, to_utc, ext in on.build_requests(now):
            if key.startswith("coop"):
                continue
            end = url.split("name/")[1].split("/")[0].split(",")[1]
            assert end >= now.strftime("%Y-%m-%d"), \
                "SNOTEL window must cover today"


def test_snotel_parser_skips_comments_missing_and_nonfinite():
    text = ("# warning preamble\n"
            "Date,Snow Depth (in)\n"
            "2026-11-26 10:00,M\n"
            "2026-11-26 11:00,\n"
            "2026-11-26 11:30,notanumber\n"
            "2026-11-26 12:00,41.2\n")
    out = on.snotel_newest(text)
    assert out == datetime(2026, 11, 26, 12, 0)


def test_snotel_parser_all_missing_returns_none():
    assert on.snotel_newest(
        "Date,Snow Depth (in)\n2026-11-26 10:00,M\n") is None


def test_coop_parser_none_rows_do_not_censor_newest():
    text = ("station,day,snowd_in\n"
            "MMNV1,2026-11-24,5.0\n"
            "MMNV1,2026-11-25,None\n"
            "MMNV1,2026-11-26,None\n")
    assert on.coop_newest(text) == datetime(2026, 11, 24)
