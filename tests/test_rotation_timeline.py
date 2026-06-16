import pandas as pd

from src.pipeline.rotation_timeline import (
    build_rotation_timeline,
    leader_changes,
    weekly_rank,
)


def test_timeline_shape_and_rank():
    hist = pd.DataFrame(
        {
            "date": ["2026-04-01", "2026-04-01", "2026-04-02", "2026-04-02"],
            "sector": ["证券", "电子", "证券", "电子"],
            "pct_chg": [2.0, -1.0, 1.0, 3.0],
            "amount": [5e10, 4e10, 5e10, 6e10],
            "main_net_inflow": [3e8, -1e8, 2e8, 4e8],
        }
    )

    tl = build_rotation_timeline(hist)
    wk = weekly_rank(tl)

    assert {"date", "sector", "strength", "rank"} <= set(tl.columns)
    assert tl.loc[tl["date"] == "2026-04-01"].sort_values("rank").iloc[0]["sector"] == "证券"
    assert {"week", "sector", "rank"} <= set(wk.columns)


def test_leader_changes_reports_weekly_handoff():
    weekly = pd.DataFrame(
        {
            "week": ["2026-14", "2026-14", "2026-15", "2026-15"],
            "sector": ["证券", "电子", "证券", "电子"],
            "rank": [1, 2, 2, 1],
            "strength": [8.0, 2.0, 1.0, 9.0],
        }
    )

    changes = leader_changes(weekly)

    assert changes["leaders"] == ["证券", "电子"]
    assert changes["path"] == "证券→电子"
    assert changes["segments"][0]["sector"] == "证券"
