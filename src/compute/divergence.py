"""Sector divergence and hedge detection."""

from __future__ import annotations

from itertools import combinations

import pandas as pd

DEFENSIVE_ROOTS = (
    "银行",
    "保险",
    "证券",
    "非银金融",
    "公用",
    "煤炭",
    "钢铁",
    "石油",
    "建筑",
    "房地产",
)
GROWTH_ROOTS = (
    "电子",
    "半导体",
    "计算机",
    "通信",
    "电力设备",
    "新能源",
    "光学光电子",
    "消费电子",
    "军工电子",
)


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


def has_correlation_coverage(selected: list[str], corr: pd.DataFrame) -> bool:
    if corr is None or corr.empty or len(selected) < 2:
        return False
    unique = list(dict.fromkeys(str(item) for item in selected))
    for left, right in combinations(unique, 2):
        value = _corr_value(corr, left, right)
        if pd.isna(value):
            return False
    return True


def structural_hedge_pairs(selected: list[str]) -> list[list[str]]:
    pairs = []
    unique = list(dict.fromkeys(str(item) for item in selected))
    for left, right in combinations(unique, 2):
        if _is_defensive(left) and _is_growth(right):
            pairs.append([left, right])
        elif _is_growth(left) and _is_defensive(right):
            pairs.append([left, right])
    return pairs


def _corr_value(corr: pd.DataFrame, left: str, right: str):
    if left not in corr.index or right not in corr.columns:
        return pd.NA
    return corr.loc[left, right]


def _is_defensive(sector: str) -> bool:
    return _matches_any(sector, DEFENSIVE_ROOTS)


def _is_growth(sector: str) -> bool:
    return _matches_any(sector, GROWTH_ROOTS)


def _matches_any(sector: str, roots: tuple[str, ...]) -> bool:
    text = str(sector)
    return any(text.startswith(root) or root in text for root in roots)
