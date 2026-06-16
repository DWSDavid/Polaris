"""Medium-term cycle helpers for sector rotation."""

from __future__ import annotations

import pandas as pd


def box_range(closes: pd.Series, window: int = 120) -> tuple[float, float]:
    series = pd.to_numeric(closes, errors="coerce").dropna()
    if series.empty:
        return 0.0, 0.0
    tail = series.tail(max(1, int(window)))
    return float(tail.max()), float(tail.min())


def position_in_box(price: float, high: float, low: float) -> float:
    high_value = float(high)
    low_value = float(low)
    price_value = float(price)
    if high_value == low_value:
        return 0.5
    position = (price_value - low_value) / (high_value - low_value)
    return max(0.0, min(1.0, float(position)))


def midterm_trend(closes: pd.Series, short: int = 20, long: int = 60) -> int:
    series = pd.to_numeric(closes, errors="coerce").dropna()
    if len(series) < max(short, long):
        return 0
    short_ma = float(series.tail(short).mean())
    long_ma = float(series.tail(long).mean())
    if short_ma > long_ma:
        return 1
    if short_ma < long_ma:
        return -1
    return 0


def cum_inflow(daily_net_inflow: pd.Series, window: int = 60) -> float:
    series = pd.to_numeric(daily_net_inflow, errors="coerce").fillna(0)
    if series.empty:
        return 0.0
    return float(series.tail(max(1, int(window))).sum())
