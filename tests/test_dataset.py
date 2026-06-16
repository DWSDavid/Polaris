import pandas as pd

from src.research.dataset import build_dataset


def test_build_dataset_labels_future_relative_winners_without_tail_leakage():
    timeline = pd.DataFrame(
        {
            "week": [1, 1, 2, 2, 3, 3],
            "sector": ["A", "B", "A", "B", "A", "B"],
            "pct_chg": [0.0, 0.0, 5.0, 1.0, 3.0, 0.0],
            "flow_strength": [0.8, 0.2, 0.6, 0.1, 0.5, 0.4],
            "trend_days": [4, 1, 5, 1, 6, 1],
        }
    )

    got = build_dataset(
        timeline,
        feature_cols=["flow_strength", "trend_days"],
        horizon_weeks=1,
        win_threshold=0.0,
    )

    assert {"week", "sector", "label", "fwd_return_1w"} <= set(got.columns)
    assert got["week"].max() == 2
    first_a = got[(got["week"] == 1) & (got["sector"] == "A")].iloc[0]
    first_b = got[(got["week"] == 1) & (got["sector"] == "B")].iloc[0]
    assert first_a["label"] == 1
    assert first_b["label"] == 0
    assert first_a["flow_strength"] == 0.8
    assert first_a["trend_days"] == 4


def test_build_dataset_adds_missing_feature_columns_as_zero_and_sorts_time():
    timeline = pd.DataFrame(
        {
            "week": [2, 1, 2, 1],
            "sector": ["A", "A", "B", "B"],
            "pct_chg": [2.0, 0.0, 0.0, 0.0],
            "score": [0.7, 0.5, 0.2, 0.1],
        }
    )

    got = build_dataset(
        timeline,
        feature_cols=["score", "missing_feature"],
        horizon_weeks=1,
        win_threshold=-1.0,
    )

    assert "missing_feature" in got.columns
    assert got["missing_feature"].eq(0).all()
    assert got[["week", "sector"]].to_records(index=False).tolist() == sorted(
        got[["week", "sector"]].to_records(index=False).tolist()
    )
