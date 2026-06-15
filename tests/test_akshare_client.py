from unittest.mock import patch

import pandas as pd

from src.data import akshare_client as ac


def test_daily_hist_uses_cache(tmp_path):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    fake = pd.DataFrame(
        {"date": ["2026-05-29"], "close": [10.0], "amount": [1e8]}
    )
    with patch.object(ac, "_raw_daily_hist", return_value=fake) as raw:
        d1 = ac.daily_hist("SH600519", "20260101", "20260529")
        ac.daily_hist("SH600519", "20260101", "20260529")
    assert raw.call_count == 1
    assert list(d1["close"]) == [10.0]


def test_daily_hist_retries_transient_failure(tmp_path):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    fake = pd.DataFrame(
        {"date": ["2026-05-29"], "close": [10.0], "amount": [1e8]}
    )
    with patch.object(
        ac,
        "_raw_daily_hist",
        side_effect=[ConnectionError("temporary"), ConnectionError("again"), fake],
    ) as raw:
        data = ac.daily_hist("SH600519", "20260101", "20260529")
    assert raw.call_count == 3
    assert list(data["close"]) == [10.0]
