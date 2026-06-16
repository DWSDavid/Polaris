import pandas as pd

from src.research.backtest import evaluate_signal, forward_return


def test_ignition_signal_forward_return():
    panel_ts = pd.DataFrame(
        {
            "week": [1, 1, 2, 2, 3, 3],
            "sector": ["A", "B", "A", "B", "A", "B"],
            "signal": [True, False, False, False, False, False],
            "fwd_return_2w": [0.06, -0.01, 0.0, 0.0, 0.0, 0.0],
        }
    )

    res = evaluate_signal(panel_ts, signal_col="signal", return_col="fwd_return_2w")

    assert res["n"] == 1
    assert res["hit_rate"] == 1.0
    assert res["avg_return"] > 0.05


def test_evaluate_signal_reports_baseline_and_drawdown():
    panel_ts = pd.DataFrame(
        {
            "signal": [True, True, False, False],
            "fwd_return_1w": [0.03, -0.02, 0.01, -0.01],
        }
    )

    res = evaluate_signal(panel_ts, signal_col="signal", return_col="fwd_return_1w")

    assert res["n"] == 2
    assert res["baseline_hit_rate"] == 0.5
    assert res["median_return"] == 0.005
    assert res["max_drawdown"] <= 0


def test_forward_return_uses_future_sector_performance_minus_cross_section_baseline():
    timeline = pd.DataFrame(
        {
            "week": [1, 1, 2, 2, 3, 3],
            "sector": ["A", "B", "A", "B", "A", "B"],
            "pct_chg": [1.0, 0.0, 4.0, 1.0, 2.0, 0.0],
        }
    )

    got = forward_return(timeline, weeks=2)
    first_a = got[(got["week"] == 1) & (got["sector"] == "A")].iloc[0]
    first_b = got[(got["week"] == 1) & (got["sector"] == "B")].iloc[0]

    assert first_a["fwd_return_2w"] > 0
    assert first_b["fwd_return_2w"] < 0
    assert got[got["week"] == 3]["fwd_return_2w"].isna().all()
