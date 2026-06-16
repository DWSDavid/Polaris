import pandas as pd

from src.compute.trend_v2 import inflow_streak_days, streak_days, turning_point_flag


def test_streak_up():
    pct = pd.Series([-1, 0.5, 1.0, 2.0, 0.3])

    assert streak_days(pct) == 3


def test_streak_down_returns_negative_days():
    pct = pd.Series([1, -0.5, -1.0, -2.0])

    assert streak_days(pct) == -3


def test_zero_breaks_streak():
    pct = pd.Series([-1, 0, 1.0, 2.0, 0.3])

    assert streak_days(pct) == 3


def test_inflow_streak():
    flow = pd.Series([1e8, 2e8, 3e8, 1e8])

    assert inflow_streak_days(flow) == 4


def test_turning_point_when_inflow_flips():
    flow = pd.Series([3e8, 2e8, 1e8, -5e7])

    assert turning_point_flag(flow, pct=pd.Series([2, 1, 0.5, -1])) is True


def test_turning_point_when_price_rises_but_flow_weakens():
    flow = pd.Series([5e8, 4e8, 2e8])

    assert turning_point_flag(flow, pct=pd.Series([1.0, 1.2, 1.5])) is True
