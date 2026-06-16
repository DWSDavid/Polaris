"""Training dataset assembly without future leakage."""

from __future__ import annotations

import pandas as pd

from src.research.backtest import forward_return


def build_dataset(
    timeline: pd.DataFrame,
    feature_cols: list[str],
    horizon_weeks: int = 2,
    win_threshold: float = 0.0,
) -> pd.DataFrame:
    if timeline.empty:
        return pd.DataFrame(columns=["week", "sector", *feature_cols, "label"])
    frame = timeline.copy()
    if "week" not in frame.columns:
        frame["week"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%G-%V")
    for column in feature_cols:
        if column not in frame.columns:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    with_returns = forward_return(frame, weeks=horizon_weeks)
    return_col = f"fwd_return_{horizon_weeks}w"
    dataset = with_returns.dropna(subset=[return_col]).copy()
    dataset["label"] = (pd.to_numeric(dataset[return_col], errors="coerce") > float(win_threshold)).astype(int)
    keep = ["week", "sector", *feature_cols, return_col, "label"]
    absolute_col = f"fwd_absolute_return_{horizon_weeks}w"
    if absolute_col in dataset.columns:
        keep.insert(-1, absolute_col)
    return dataset[keep].sort_values(["week", "sector"]).reset_index(drop=True)
