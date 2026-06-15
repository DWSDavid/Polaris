import pandas as pd

from src.compute.trend import consecutive_up_days, trend_sign


def test_trend_sign_up():
    closes = pd.Series(
        [
            10,
            10,
            11,
            12,
            13,
            14,
            15,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
            23,
            24,
            25,
            26,
            27,
            28,
            30,
        ]
    )

    assert trend_sign(closes, window=20) == 1


def test_trend_sign_down():
    closes = pd.Series(list(range(30, 9, -1)))

    assert trend_sign(closes, window=20) == -1


def test_trend_sign_neutral_when_history_is_short():
    closes = pd.Series([10, 11, 12])

    assert trend_sign(closes, window=20) == 0


def test_consecutive_up_days_counts_trailing_positive_days():
    pct = pd.Series([1.0, -0.5, 2.0, 1.0, 0.5])

    assert consecutive_up_days(pct) == 3
