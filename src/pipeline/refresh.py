"""End-of-day orchestration helpers."""

import pandas as pd

from src.compute import config, indicators
from src.compute.state_machine import classify_state
from src.data import cache


def build_sector_panel(features: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    out["strength"] = indicators.sector_strength(features, config.STRENGTH_WEIGHTS)
    out["strength_rank"] = out["strength"].rank(pct=True)
    out["state"] = [
        classify_state(
            row.strength_rank,
            row.diffusion,
            row.fund_inflow,
            row.volume_amp,
            row.trend20,
            row.consecutive_up,
        )
        for row in out.itertuples()
    ]
    return out


def _sample_features() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "relative_return": [0.02, -0.01, 0.01],
            "volume_amp": [1.3, 0.9, 2.2],
            "fund_flow": [1e8, -1e8, 5e7],
            "breadth": [0.7, 0.3, 0.62],
            "leader_contrib": [0.5, 0.9, 0.65],
            "diffusion": [0.7, 0.3, 0.62],
            "fund_inflow": [True, False, True],
            "trend20": [1, 1, 1],
            "consecutive_up": [2, 1, 4],
        },
        index=["证券", "半导体", "主要消费"],
    )


def refresh_eod() -> pd.DataFrame:
    hit = cache.read("pipeline", "sector_panel", "latest")
    if hit is not None:
        return hit.set_index("sector") if "sector" in hit.columns else hit

    panel = build_sector_panel(_sample_features())
    cache.write("pipeline", "sector_panel", "latest", panel.reset_index(names="sector"))
    return panel
