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
