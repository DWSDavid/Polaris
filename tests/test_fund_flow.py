import pandas as pd

from src.pipeline.refresh import aggregate_main_inflow


def test_aggregate_main_inflow_by_sector():
    stocks = pd.DataFrame(
        {
            "symbol": ["SH600519", "SZ000858", "SH600000"],
            "sector": ["主要消费", "主要消费", "金融"],
        }
    )
    flows = {
        "SH600519": pd.DataFrame({"主力净流入-净额": [100_000_000.0]}),
        "SZ000858": pd.DataFrame({"主力净流入-净额": [-30_000_000.0]}),
        "SH600000": pd.DataFrame({"主力净流入-净额": [-50_000_000.0]}),
    }

    out = aggregate_main_inflow(stocks, flows)

    assert out["主要消费"] == 70_000_000.0
    assert out["金融"] == -50_000_000.0


def test_aggregate_main_inflow_ignores_empty_frames():
    stocks = pd.DataFrame({"symbol": ["SH600519"], "sector": ["主要消费"]})

    out = aggregate_main_inflow(stocks, {"SH600519": pd.DataFrame()})

    assert out == {}
