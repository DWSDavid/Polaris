"""Backtest helpers for grounded sector signals."""

from __future__ import annotations

import pandas as pd


def evaluate_signal(
    df: pd.DataFrame,
    signal_col: str,
    return_col: str,
) -> dict:
    frame = df.copy()
    if frame.empty or signal_col not in frame.columns or return_col not in frame.columns:
        return _empty_result()

    returns = pd.to_numeric(frame[return_col], errors="coerce")
    signal = frame[signal_col].fillna(False).astype(bool)
    selected = returns[signal].dropna()
    baseline = returns.dropna()
    if selected.empty:
        result = _empty_result()
    else:
        result = {
            "n": int(len(selected)),
            "hit_rate": float((selected > 0).mean()),
            "avg_return": float(selected.mean()),
            "median_return": round(float(selected.median()), 10),
            "max_drawdown": float(_max_drawdown(selected)),
        }
    result["baseline_n"] = int(len(baseline))
    result["baseline_hit_rate"] = float((baseline > 0).mean()) if len(baseline) else 0.0
    result["baseline_avg_return"] = float(baseline.mean()) if len(baseline) else 0.0
    return result


def forward_return(timeline: pd.DataFrame, weeks: int = 2) -> pd.DataFrame:
    if timeline.empty:
        return timeline.copy()
    frame = timeline.copy()
    if "week" not in frame.columns:
        frame["week"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%G-%V")
    frame["pct_chg"] = pd.to_numeric(frame.get("pct_chg"), errors="coerce").fillna(0.0)
    weekly = (
        frame.groupby(["week", "sector"], as_index=False)["pct_chg"]
        .sum()
        .sort_values(["sector", "week"])
    )
    absolute_col = f"fwd_absolute_return_{weeks}w"
    return_col = f"fwd_return_{weeks}w"
    weekly[absolute_col] = weekly.groupby("sector")["pct_chg"].transform(
        lambda series: _future_sum(series, weeks)
    ) / 100.0
    baseline = weekly.groupby("week")[absolute_col].transform("mean")
    weekly[return_col] = weekly[absolute_col] - baseline
    return frame.merge(
        weekly[["week", "sector", absolute_col, return_col]],
        on=["week", "sector"],
        how="left",
    )


def _empty_result() -> dict:
    return {
        "n": 0,
        "hit_rate": 0.0,
        "avg_return": 0.0,
        "median_return": 0.0,
        "max_drawdown": 0.0,
        "baseline_n": 0,
        "baseline_hit_rate": 0.0,
        "baseline_avg_return": 0.0,
    }


def _max_drawdown(returns: pd.Series) -> float:
    curve = (1 + pd.to_numeric(returns, errors="coerce").fillna(0.0)).cumprod()
    running_max = curve.cummax()
    drawdown = curve / running_max - 1
    return float(drawdown.min()) if not drawdown.empty else 0.0


def _future_sum(series: pd.Series, weeks: int) -> pd.Series:
    total = pd.Series(0.0, index=series.index)
    for step in range(1, max(1, int(weeks)) + 1):
        total = total + series.shift(-step)
    valid = series.shift(-max(1, int(weeks))).notna()
    return total.where(valid)
