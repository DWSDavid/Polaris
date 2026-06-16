import pandas as pd

from src.compute.mainline import mainline_breakdown, mainline_score, pick_mainline


def test_sustained_beats_one_day_pop():
    panel = pd.DataFrame(
        {
            "sector": ["稀土", "证券"],
            "pct_chg": [9.0, 1.2],
            "inflow_10d": [0.2e8, 30e8],
            "trend_days": [1, 6],
            "diffusion": [0.3, 0.7],
            "amount": [2e9, 6e10],
        }
    )

    scored = mainline_score(panel)

    assert pick_mainline(scored) == "证券"


def test_breakdown_reports_components():
    scored = mainline_score(
        pd.DataFrame(
            {
                "sector": ["证券", "电子"],
                "pct_chg": [1.2, 0.8],
                "inflow_10d": [30e8, 5e8],
                "trend_days": [6, 2],
                "diffusion": [0.7, 0.4],
                "amount": [6e10, 4e10],
            }
        )
    )

    parts = mainline_breakdown(scored.iloc[0])

    assert "10日资金" in parts
    assert "持续" in parts
    assert "扩散" in parts
    assert "成交" in parts
