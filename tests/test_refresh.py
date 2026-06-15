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
