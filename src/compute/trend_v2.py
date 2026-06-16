"""Medium-term trend and turning-point helpers for Polaris v2."""

from __future__ import annotations

import pandas as pd


def streak_days(pct: pd.Series) -> int:
    clean = pd.to_numeric(pct, errors="coerce").dropna()
    if clean.empty or clean.iloc[-1] == 0:
        return 0
    sign = 1 if clean.iloc[-1] > 0 else -1
    count = 0
    for value in reversed(clean.tolist()):
        if value == 0:
            break
        if (value > 0 and sign > 0) or (value < 0 and sign < 0):
            count += 1
        else:
            break
    prior_index = len(clean) - count - 1
    # Plan口径: 负转正首日是低位修复确认日, 不计入主升持续天数。
    if sign > 0 and prior_index >= 0 and clean.iloc[prior_index] < 0:
        count = max(0, count - 1)
    return sign * count


def inflow_streak_days(flow: pd.Series) -> int:
    clean = pd.to_numeric(flow, errors="coerce").dropna()
    total = 0
    for value in reversed(clean.tolist()):
        if value <= 0:
            break
        total += 1
    return total


def turning_point_flag(flow: pd.Series, pct: pd.Series) -> bool:
    flow_clean = pd.to_numeric(flow, errors="coerce").dropna()
    pct_clean = pd.to_numeric(pct, errors="coerce").dropna()
    if len(flow_clean) < 2:
        return False
    if flow_clean.iloc[-2] > 0 and flow_clean.iloc[-1] < 0:
        return True
    if len(flow_clean) >= 3 and len(pct_clean) >= 3:
        recent_flow = flow_clean.iloc[-3:]
        recent_pct = pct_clean.iloc[-3:]
        flow_weakens = recent_flow.is_monotonic_decreasing
        price_strengthens = recent_pct.iloc[-1] > 0 and recent_pct.is_monotonic_increasing
        if flow_weakens and price_strengthens:
            return True
    return False
