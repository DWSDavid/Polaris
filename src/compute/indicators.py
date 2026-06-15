"""Sector indicator helpers."""

import pandas as pd


def diffusion_rate(pct_changes: pd.Series) -> float:
    count = pct_changes.notna().sum()
    return float((pct_changes > 0).sum() / count) if count else 0.0


def leader_contribution(turnover: pd.Series, top_n: int = 3) -> float:
    total = turnover.sum()
    if total <= 0:
        return 0.0
    return float(turnover.nlargest(top_n).sum() / total)


def volume_amplification(turnover_hist: pd.Series, window: int = 20) -> float:
    if len(turnover_hist) == 0:
        return 0.0
    avg = turnover_hist.tail(window).mean()
    return float(turnover_hist.iloc[-1] / avg) if avg else 0.0


def zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    return (series - series.mean()) / std if std else series * 0.0


def sector_strength(features: pd.DataFrame, weights: dict) -> pd.Series:
    score = pd.Series(0.0, index=features.index)
    for column, weight in weights.items():
        score = score + weight * zscore(features[column])
    return score
