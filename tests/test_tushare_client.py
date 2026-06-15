from unittest.mock import patch

import pandas as pd

from src.data import tushare_client as tc


def test_to_ts_code():
    assert tc.to_ts_code("SH600519") == "600519.SH"
    assert tc.to_ts_code("SZ000858") == "000858.SZ"


def test_daily_cached(tmp_path):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    fake = pd.DataFrame(
        {"trade_date": ["20260529"], "close": [1700.0], "amount": [1e6]}
    )
    with patch.object(tc, "_raw_daily", return_value=fake) as raw:
        tc.daily("SH600519", "20260101", "20260529")
        tc.daily("SH600519", "20260101", "20260529")
    assert raw.call_count == 1
