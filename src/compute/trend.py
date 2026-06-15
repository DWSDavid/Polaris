"""Trend helpers computed from ordered daily price series."""

import pandas as pd


def trend_sign(closes: pd.Series, window: int = 20) -> int:
    clean = pd.to_numeric(closes, errors="coerce").dropna()
    if len(clean) < window + 1:
        return 0
    ref = clean.iloc[-(window + 1)]
    now = clean.iloc[-1]
    if now > ref:
        return 1
    if now < ref:
        return -1
    return 0


def consecutive_up_days(pct: pd.Series) -> int:
    total = 0
    for value in reversed(pd.to_numeric(pct, errors="coerce").dropna().tolist()):
        if value <= 0:
            break
        total += 1
    return total
