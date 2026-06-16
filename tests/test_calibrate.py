import pandas as pd

from src.research.calibrate import calibrate_threshold, walk_forward_splits


def test_walk_forward_splits_keep_time_order_and_hold_out_future():
    dates = pd.Series(range(1, 13))

    splits = walk_forward_splits(dates, k=3)

    assert len(splits) == 3
    for train_idx, test_idx in splits:
        assert max(dates.iloc[train_idx]) < min(dates.iloc[test_idx])
        assert list(dates.iloc[test_idx]) == sorted(dates.iloc[test_idx])


def test_calibrate_threshold_reports_in_and_out_sample_vs_baseline():
    df = pd.DataFrame(
        {
            "week": list(range(1, 13)),
            "score": [0.2, 0.7, 0.8, 0.1, 0.75, 0.85, 0.15, 0.78, 0.82, 0.2, 0.72, 0.88],
            "fwd_return": [-0.02, 0.03, 0.04, -0.01, 0.05, 0.06, -0.03, 0.04, 0.05, -0.02, 0.03, 0.07],
        }
    )

    res = calibrate_threshold(
        df,
        grid=[0.3, 0.6, 0.9],
        objective="hit_rate_return",
        score_col="score",
        return_col="fwd_return",
        date_col="week",
        k=3,
    )

    assert res["best"] == 0.6
    assert res["in_sample"]["hit_rate"] > res["in_sample"]["baseline_hit_rate"]
    assert res["out_sample"]["hit_rate"] > res["out_sample"]["baseline_hit_rate"]
    assert "oos_beats_baseline" in res


def test_calibrate_threshold_marks_oos_not_better_when_signal_fails_future():
    df = pd.DataFrame(
        {
            "week": list(range(1, 13)),
            "score": [0.8, 0.7, 0.9, 0.8, 0.75, 0.7, 0.9, 0.85, 0.8, 0.75, 0.9, 0.8],
            "fwd_return": [0.04, 0.03, 0.05, 0.02, -0.04, -0.03, -0.02, -0.05, -0.01, -0.02, -0.03, -0.04],
        }
    )

    res = calibrate_threshold(
        df,
        grid=[0.6, 0.8],
        objective="hit_rate_return",
        score_col="score",
        return_col="fwd_return",
        date_col="week",
        k=3,
    )

    assert res["oos_beats_baseline"] is False
