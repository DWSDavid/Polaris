import pandas as pd

from src.data import cache


def test_roundtrip(tmp_path):
    cache.CACHE_DIR = tmp_path
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    cache.write("akshare", "hist", "SH600519", df)
    assert cache.exists("akshare", "hist", "SH600519")
    got = cache.read("akshare", "hist", "SH600519")
    pd.testing.assert_frame_equal(got, df)


def test_missing_returns_none(tmp_path):
    cache.CACHE_DIR = tmp_path
    assert cache.read("akshare", "hist", "NOPE") is None
    assert cache.exists("akshare", "hist", "NOPE") is False
