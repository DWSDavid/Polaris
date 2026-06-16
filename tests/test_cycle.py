import pandas as pd

from src.compute.cycle import box_range, cum_inflow, midterm_trend, position_in_box


def test_box_and_position():
    closes = pd.Series([10, 11, 9, 12, 8, 13, 10])

    hi, lo = box_range(closes, window=7)

    assert hi == 13 and lo == 8
    assert abs(position_in_box(10, hi, lo) - 0.4) < 1e-9


def test_midterm_trend_up():
    closes = pd.Series(list(range(1, 80)))

    assert midterm_trend(closes, short=20, long=60) == 1


def test_cum_inflow_60d():
    flow = pd.Series([1e8] * 60)

    assert abs(cum_inflow(flow, window=60) - 60e8) < 1.0
