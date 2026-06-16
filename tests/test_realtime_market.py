import pandas as pd
import time

from src.data.akshare_client import (
    normalize_industry_spot,
    normalize_realtime_stock_spot,
    normalize_sector_fund_flow,
)
from src.pipeline.realtime import build_realtime_industry_panel, join_universe_realtime
from src.pipeline import realtime


def test_normalize_realtime_stock_spot_from_eastmoney_columns():
    raw = pd.DataFrame(
        [
            {
                "代码": "600000",
                "名称": "浦发银行",
                "最新价": 8.12,
                "涨跌幅": 1.2,
                "成交额": 123456789.0,
                "量比": 1.4,
                "换手率": 0.8,
                "市盈率-动态": 6.5,
                "市净率": 0.6,
                "总市值": 300000000000.0,
            }
        ]
    )

    got = normalize_realtime_stock_spot(raw)

    assert got.loc[0, "code"] == "600000"
    assert got.loc[0, "symbol"] == "SH600000"
    assert got.loc[0, "latest_price"] == 8.12
    assert got.loc[0, "amount"] == 123456789.0
    assert got.loc[0, "pe_ttm"] == 6.5


def test_normalize_industry_spot_from_board_columns():
    raw = pd.DataFrame(
        [
            {
                "板块名称": "银行",
                "板块代码": "BK0475",
                "涨跌幅": 0.8,
                "总市值": 12000000000000.0,
                "换手率": 0.9,
                "上涨家数": 28,
                "下跌家数": 12,
                "领涨股票": "招商银行",
                "领涨股票-涨跌幅": 3.2,
            }
        ]
    )

    got = normalize_industry_spot(raw)

    assert got.loc[0, "industry"] == "银行"
    assert got.loc[0, "industry_code"] == "BK0475"
    assert got.loc[0, "pct_chg"] == 0.8
    assert got.loc[0, "up_count"] == 28


def test_build_realtime_industry_panel_merges_fund_flow():
    industry = pd.DataFrame(
        [
            {
                "industry": "银行",
                "industry_code": "BK0475",
                "pct_chg": 0.8,
                "total_mv": 100.0,
                "turnover_rate": 0.9,
                "up_count": 28,
                "down_count": 12,
                "leading_stock": "招商银行",
                "leading_stock_pct_chg": 3.2,
            }
        ]
    )
    flows = pd.DataFrame(
        [
            {
                "industry": "银行",
                "today_main_net_inflow": 250000000.0,
                "today_main_net_inflow_pct": 4.1,
            }
        ]
    )

    panel = build_realtime_industry_panel(industry, flows)

    assert panel.loc[0, "fund_flow_yi"] == 2.5
    assert panel.loc[0, "money_direction"] == "净流入"
    assert panel.loc[0, "diffusion"] == 0.7
    assert panel.loc[0, "data_quality"] == "realtime_snapshot"


def test_join_universe_realtime_enriches_only_leader_pool():
    universe = pd.DataFrame(
        {
            "code": ["600000"],
            "symbol": ["SH600000"],
            "name": ["浦发银行"],
            "sector": ["金融"],
        }
    )
    spot = pd.DataFrame(
        {
            "code": ["600000", "000001"],
            "latest_price": [8.12, 12.0],
            "pct_chg": [1.2, -0.2],
            "amount": [123.0, 456.0],
        }
    )

    got = join_universe_realtime(universe, spot)

    assert len(got) == 1
    assert got.loc[0, "latest_price"] == 8.12
    assert got.loc[0, "data_quality"] == "realtime_snapshot"


def test_safe_realtime_industry_panel_falls_back_to_cache(tmp_path, monkeypatch):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    cached = pd.DataFrame(
        [
            {
                "industry": "银行",
                "pct_chg": 1.0,
                "fund_flow_yi": 2.0,
                "data_quality": "realtime_snapshot",
            }
        ]
    )
    cache.write("pipeline", "realtime_industry_panel", "latest", cached)

    def explode():
        raise RuntimeError("akshare down")

    monkeypatch.setattr(realtime, "refresh_realtime_industry_panel", explode)

    panel, error = realtime.safe_realtime_industry_panel()

    assert panel.loc[0, "industry"] == "银行"
    assert "akshare down" in error


def test_safe_realtime_industry_panel_times_out_to_cache(tmp_path, monkeypatch):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    cached = pd.DataFrame(
        [
            {
                "industry": "电子",
                "pct_chg": 2.0,
                "fund_flow_yi": 1.0,
                "data_quality": "realtime_snapshot",
            }
        ]
    )
    cache.write("pipeline", "realtime_industry_panel", "latest", cached)

    def slow_refresh():
        time.sleep(0.05)
        return pd.DataFrame({"industry": ["通信"]})

    monkeypatch.setattr(realtime, "refresh_realtime_industry_panel", slow_refresh)

    panel, error = realtime.safe_realtime_industry_panel(timeout_seconds=0.01)

    assert panel.loc[0, "industry"] == "电子"
    assert "超时" in error


def test_safe_realtime_industry_panel_returns_empty_when_no_cache(
    tmp_path, monkeypatch
):
    from src.data import cache

    cache.CACHE_DIR = tmp_path

    def explode():
        raise RuntimeError("akshare down")

    monkeypatch.setattr(realtime, "refresh_realtime_industry_panel", explode)

    panel, error = realtime.safe_realtime_industry_panel()

    assert panel.empty
    assert "akshare down" in error
