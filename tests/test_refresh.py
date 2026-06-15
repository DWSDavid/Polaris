import pandas as pd

from src.pipeline import refresh


def test_build_sector_panel_schema():
    features = pd.DataFrame(
        {
            "relative_return": [0.02, -0.01],
            "volume_amp": [1.3, 0.9],
            "fund_flow": [1e8, -1e8],
            "breadth": [0.7, 0.3],
            "leader_contrib": [0.5, 0.9],
            "diffusion": [0.7, 0.3],
            "fund_inflow": [True, False],
            "trend20": [1, 1],
            "consecutive_up": [2, 1],
        },
        index=["证券", "半导体"],
    )
    panel = refresh.build_sector_panel(features)
    assert "strength" in panel.columns
    assert "state" in panel.columns
    assert panel.loc["证券", "state"] == "主升扩散"


def test_build_universe_panels_from_seed():
    sector_panel, stock_panel = refresh.build_universe_panels()

    assert len(sector_panel) == 11
    assert len(stock_panel) == 110
    assert {"sector", "name", "symbol", "sector_state", "is_top_leader"} <= set(
        stock_panel.columns
    )
    assert {"stock_count", "top_leaders", "coverage", "state_note"} <= set(
        sector_panel.columns
    )
    assert {"risk_level", "action_hint", "watch_points"} <= set(sector_panel.columns)
    assert {"stock_role", "momentum_flag"} <= set(stock_panel.columns)
    assert sector_panel.loc["主要消费", "stock_count"] == 10
    assert "贵州茅台" in sector_panel.loc["主要消费", "top_leaders"]


def test_refresh_eod_uses_seed_universe_when_cache_missing(tmp_path):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    panel = refresh.refresh_eod()

    assert len(panel) == 11
    assert "主要消费" in panel.index
    assert cache.exists("pipeline", "sector_panel", "latest")
    assert cache.exists("pipeline", "stock_panel", "latest")


def test_refresh_eod_rebuilds_stale_sector_cache(tmp_path):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    stale = pd.DataFrame(
        {
            "sector": ["旧缓存"],
            "stock_count": [1],
            "top_leaders": ["A"],
            "coverage": [1.0],
            "state_note": ["missing explanation fields"],
        }
    )
    cache.write("pipeline", "sector_panel", "latest", stale)

    panel = refresh.refresh_eod()

    assert "risk_level" in panel.columns
    assert "旧缓存" not in panel.index


def test_refresh_eod_prefers_market_when_fetcher_is_given(tmp_path):
    from src.data import cache

    cache.CACHE_DIR = tmp_path

    def daily_fetcher(symbol, start, end):
        return pd.DataFrame(
            {
                "trade_date": pd.date_range("2026-05-20", periods=21).strftime(
                    "%Y%m%d"
                ),
                "close": list(range(10, 31)),
                "pct_chg": [0.5] * 21,
                "amount": [1000.0] * 21,
            }
        )

    panel = refresh.refresh_eod(
        start="20260520",
        end="20260612",
        daily_fetcher=daily_fetcher,
        basic_fetcher=refresh.empty_basic_fetcher,
        limit=3,
    )

    assert panel["data_quality"].eq("market_snapshot").all()
    assert panel["signals_confirmed"].all()


def test_refresh_eod_falls_back_honestly_when_market_is_empty(tmp_path):
    from src.data import cache

    cache.CACHE_DIR = tmp_path

    def empty_fetcher(symbol, start, end):
        return pd.DataFrame()

    panel = refresh.refresh_eod(
        start="20260520",
        end="20260612",
        daily_fetcher=empty_fetcher,
        basic_fetcher=empty_fetcher,
        limit=3,
    )

    assert panel["data_quality"].eq("seed_static").all()
    assert (~panel["signals_confirmed"]).all()


def test_enrich_stock_panel_with_market_data():
    stock_panel = pd.DataFrame(
        {
            "sector": ["证券", "证券"],
            "symbol": ["SH600000", "SZ000001"],
            "name": ["浦发银行", "平安银行"],
            "market_cap": [1000.0, 900.0],
            "sector_share": [0.55, 0.45],
            "index_weight": [0.5, 0.4],
            "rank": [1, 2],
        }
    )
    daily = {
        "SH600000": pd.DataFrame(
            [
                {
                    "trade_date": "20260612",
                    "close": 11.0,
                    "pct_chg": 2.0,
                    "amount": 1000.0,
                }
            ]
        ),
        "SZ000001": pd.DataFrame(
            [
                {
                    "trade_date": "20260612",
                    "close": 10.0,
                    "pct_chg": -1.0,
                    "amount": 500.0,
                }
            ]
        ),
    }
    basics = {
        "SH600000": pd.DataFrame(
            [
                {
                    "trade_date": "20260612",
                    "turnover_rate": 1.2,
                    "volume_ratio": 1.5,
                    "pe_ttm": 8.0,
                    "pb": 0.8,
                    "total_mv": 100000.0,
                }
            ]
        ),
        "SZ000001": pd.DataFrame(
            [
                {
                    "trade_date": "20260612",
                    "turnover_rate": 0.8,
                    "volume_ratio": 0.9,
                    "pe_ttm": 7.0,
                    "pb": 0.7,
                    "total_mv": 90000.0,
                }
            ]
        ),
    }

    enriched = refresh.enrich_stock_panel_with_market_data(stock_panel, daily, basics)

    assert list(enriched["pct_chg"]) == [2.0, -1.0]
    assert enriched.loc[0, "latest_close"] == 11.0
    assert enriched.loc[0, "volume_ratio"] == 1.5
    assert enriched.loc[1, "pe_ttm"] == 7.0


def test_enrich_stock_panel_with_market_data_computes_real_trend():
    stock_panel = pd.DataFrame(
        {
            "sector": ["证券"],
            "symbol": ["SH600000"],
            "name": ["浦发银行"],
            "market_cap": [1000.0],
            "sector_share": [1.0],
            "index_weight": [0.5],
            "rank": [1],
        }
    )
    daily = {
        "SH600000": pd.DataFrame(
            {
                "trade_date": pd.date_range("2026-05-01", periods=21).strftime(
                    "%Y%m%d"
                ),
                "close": list(range(10, 31)),
                "pct_chg": [-0.5] + [1.0] * 20,
                "amount": [1000.0] * 21,
            }
        )
    }

    enriched = refresh.enrich_stock_panel_with_market_data(stock_panel, daily)

    assert enriched.loc[0, "trend20"] == 1
    assert enriched.loc[0, "consecutive_up"] == 20


def test_build_market_sector_panel_from_stock_market_data():
    stocks = pd.DataFrame(
        {
            "sector": ["证券", "证券", "医药"],
            "name": ["A", "B", "C"],
            "market_cap": [1000.0, 900.0, 800.0],
            "pct_chg": [2.0, -1.0, -2.0],
            "amount": [1000.0, 500.0, 300.0],
            "volume_ratio": [1.5, 0.9, 0.8],
            "sector_share": [0.55, 0.45, 1.0],
            "rank": [1, 2, 1],
            "trend20": [1, -1, -1],
            "consecutive_up": [3, 1, 0],
        }
    )

    panel = refresh.build_market_sector_panel(stocks)

    assert panel.loc["证券", "diffusion"] == 0.5
    assert panel.loc["证券", "fund_flow"] == 1.0
    assert panel.loc["医药", "fund_flow"] == -1.0
    assert "A、B" == panel.loc["证券", "top_leaders"]
    assert panel.loc["证券", "trend20"] == 0
    assert panel.loc["证券", "consecutive_up"] == 2


def test_build_market_sector_panel_can_use_real_main_inflow():
    stocks = pd.DataFrame(
        {
            "sector": ["证券", "证券"],
            "name": ["A", "B"],
            "market_cap": [1000.0, 900.0],
            "pct_chg": [-2.0, -1.0],
            "amount": [1000.0, 500.0],
            "volume_ratio": [1.5, 0.9],
            "sector_share": [0.55, 0.45],
            "rank": [1, 2],
            "trend20": [1, 1],
            "consecutive_up": [2, 2],
        }
    )

    panel = refresh.build_market_sector_panel(
        stocks,
        main_inflow_by_sector={"证券": 70_000_000.0},
    )

    assert panel.loc["证券", "fund_flow"] == 70_000_000.0
    assert panel.loc["证券", "fund_inflow"]


def test_refresh_eod_can_build_market_snapshot(tmp_path):
    from src.data import cache

    cache.CACHE_DIR = tmp_path

    def daily_fetcher(symbol, start, end):
        pct = 2.0 if symbol.endswith("600519") else -0.5
        return pd.DataFrame(
            [{"trade_date": end, "close": 10.0, "pct_chg": pct, "amount": 1000.0}]
        )

    def basic_fetcher(symbol, start, end):
        return pd.DataFrame(
            [
                {
                    "trade_date": end,
                    "turnover_rate": 1.0,
                    "volume_ratio": 1.2,
                    "pe_ttm": 10.0,
                    "pb": 1.0,
                    "total_mv": 100000.0,
                }
            ]
        )

    panel = refresh.refresh_eod(
        start="20260601",
        end="20260612",
        force_market=True,
        daily_fetcher=daily_fetcher,
        basic_fetcher=basic_fetcher,
    )
    stocks = refresh.stock_panel()

    assert panel["data_quality"].eq("market_snapshot").all()
    assert "pct_chg" in stocks.columns
    assert stocks["market_data_available"].all()
    assert "stock_role" in stocks.columns
    assert "risk_level" in panel.columns


def test_refresh_eod_caches_sector_history_track(tmp_path):
    from src.data import cache

    cache.CACHE_DIR = tmp_path

    def daily_fetcher(symbol, start, end):
        return pd.DataFrame(
            {
                "trade_date": pd.date_range("2026-06-01", periods=6).strftime("%Y%m%d"),
                "close": [10, 10.2, 10.4, 10.6, 10.8, 11.0],
                "pct_chg": [1.0, 1.2, -0.4, 1.4, 1.6, 1.8],
                "amount": [100.0, 120.0, 90.0, 130.0, 140.0, 150.0],
            }
        )

    refresh.refresh_eod(
        start="20260601",
        end="20260606",
        force_market=True,
        daily_fetcher=daily_fetcher,
        basic_fetcher=refresh.empty_basic_fetcher,
        limit=5,
    )

    history = refresh.sector_history_panel()
    stock_history = refresh.stock_history_panel()
    assert not history.empty
    assert not stock_history.empty
    assert {"trade_date", "sector", "fund_flow", "diffusion"} <= set(history.columns)
    assert {"trade_date", "symbol", "close", "pct_chg"} <= set(stock_history.columns)
    assert cache.exists("pipeline", "sector_history", "latest")
    assert cache.exists("pipeline", "stock_history", "latest")


def test_refresh_eod_keeps_daily_when_basic_is_rate_limited(tmp_path):
    from src.data import cache

    cache.CACHE_DIR = tmp_path

    def daily_fetcher(symbol, start, end):
        return pd.DataFrame(
            [{"trade_date": end, "close": 10.0, "pct_chg": 1.0, "amount": 1000.0}]
        )

    def basic_fetcher(symbol, start, end):
        raise RuntimeError("daily_basic rate limited")

    panel = refresh.refresh_eod(
        start="20260601",
        end="20260612",
        force_market=True,
        daily_fetcher=daily_fetcher,
        basic_fetcher=basic_fetcher,
    )
    stocks = refresh.stock_panel()

    assert panel["data_quality"].eq("market_snapshot").all()
    assert stocks["market_data_available"].all()
    assert stocks["pe_ttm"].isna().all()


def test_akshare_daily_fetcher_normalizes_columns():
    raw = pd.DataFrame(
        [{"date": "2024-06-07", "close": 1550.0, "pct": 1.2, "amount": 123.0}]
    )

    got = refresh.normalize_akshare_daily(raw)

    assert list(got.columns) == ["trade_date", "close", "pct_chg", "amount"]
    assert got.loc[0, "trade_date"] == "20240607"
    assert got.loc[0, "pct_chg"] == 1.2


def test_refresh_eod_limit_fetches_subset(tmp_path):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    seen = []

    def daily_fetcher(symbol, start, end):
        seen.append(symbol)
        return pd.DataFrame(
            [{"trade_date": end, "close": 10.0, "pct_chg": 1.0, "amount": 1000.0}]
        )

    panel = refresh.refresh_eod(
        start="20260601",
        end="20260612",
        force_market=True,
        daily_fetcher=daily_fetcher,
        basic_fetcher=refresh.empty_basic_fetcher,
        limit=5,
    )

    assert len(seen) == 5
    assert panel["data_quality"].eq("market_snapshot").all()


def test_provider_fetchers_support_akshare():
    daily_fetcher, basic_fetcher = refresh.provider_fetchers("akshare")

    assert daily_fetcher is refresh.akshare_daily_fetcher
    assert basic_fetcher is refresh.empty_basic_fetcher
