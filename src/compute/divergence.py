"""Sector divergence and hedge detection."""

from __future__ import annotations

from itertools import combinations

import pandas as pd


def correlation_matrix(sector_returns: pd.DataFrame) -> pd.DataFrame:
    if sector_returns.empty:
        return pd.DataFrame()
    returns = sector_returns.apply(pd.to_numeric, errors="coerce")
    return returns.corr()


def hedge_score(selected: list[str], corr: pd.DataFrame) -> float:
    pairs = hedge_pairs(selected, corr, threshold=0.0)
    if not pairs:
        return 0.0
    values = []
    for left, right in pairs:
        value = _corr_value(corr, left, right)
        if pd.notna(value) and value < 0:
            values.append(abs(float(value)))
    return max(values) if values else 0.0


def hedge_pairs(
    selected: list[str],
    corr: pd.DataFrame,
    threshold: float = -0.3,
) -> list[list[str]]:
    if corr is None or corr.empty or len(selected) < 2:
        return []
    pairs = []
    unique = list(dict.fromkeys(str(item) for item in selected))
    for left, right in combinations(unique, 2):
        value = _corr_value(corr, left, right)
        if pd.notna(value) and float(value) <= threshold:
            pairs.append([left, right])
    return pairs


def _corr_value(corr: pd.DataFrame, left: str, right: str):
    if left not in corr.index or right not in corr.columns:
        return pd.NA
    return corr.loc[left, right]
