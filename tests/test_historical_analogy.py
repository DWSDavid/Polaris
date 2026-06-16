import pandas as pd

from src.compute.historical_analogy import build_analogy_samples, analogy_report


def test_build_analogy_samples_adds_forward_returns_and_remaining_days():
    history = pd.DataFrame(
        {
            "sector": ["证券"] * 7,
            "trade_date": pd.date_range("2026-06-01", periods=7).strftime("%Y%m%d"),
            "state": ["主升扩散"] * 7,
            "trend_days": [1, 2, 3, 4, 5, 6, 7],
            "close": [100, 102, 105, 107, 106, 108, 111],
            "pct_chg": [1.0, 2.0, 3.0, 1.9, -0.9, 1.8, 2.8],
        }
    )

    samples = build_analogy_samples(history, horizons=(1, 3), max_lookahead=5)

    row = samples.loc[samples["trade_date"] == "20260602"].iloc[0]
    assert round(row["forward_return_1d"], 4) == round(105 / 102 - 1, 4)
    assert round(row["forward_return_3d"], 4) == round(106 / 102 - 1, 4)
    assert row["remaining_positive_days"] == 2
    assert row["max_drawdown_3d"] < 0


def test_analogy_report_filters_similar_state_and_trend_days():
    samples = pd.DataFrame(
        {
            "sector": ["证券", "电子", "银行", "通信"],
            "state": ["主升扩散", "主升扩散", "低位修复", "主升扩散"],
            "trend_days": [5, 6, 5, 9],
            "remaining_positive_days": [3, 5, 1, 8],
            "forward_return_3d": [0.03, 0.05, -0.02, 0.10],
            "forward_return_5d": [0.04, -0.01, 0.01, 0.12],
            "max_drawdown_5d": [-0.02, -0.04, -0.03, -0.08],
        }
    )

    report = analogy_report(samples, state="主升扩散", trend_days=5, tolerance=1)

    assert report["sample_count"] == 2
    assert report["median_remaining_positive_days"] == 4
    assert report["win_rate_5d"] == 0.5
    assert report["median_forward_return_3d"] == 0.04
    assert "还能走" in report["summary"]
