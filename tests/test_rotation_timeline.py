import pandas as pd
import pytest

from src.pipeline.rotation_timeline import (
    build_rotation_timeline,
    filter_rotation_groups,
    heatmap_flow_matrix,
    leader_changes,
    relative_flow_heatmap_matrix,
    select_rotation_sectors,
    weekly_rank,
)


@pytest.fixture(autouse=True)
def isolate_rotation_cache(tmp_path, monkeypatch):
    from src.pipeline import rotation_timeline as rt

    monkeypatch.setattr(rt.cache, "CACHE_DIR", tmp_path / "data" / "cache")


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


def test_weekly_rank_uses_readable_week_range_not_month_like_label():
    timeline = pd.DataFrame(
        {
            "date": ["2026-06-15", "2026-06-16"],
            "sector": ["电子", "半导体"],
            "pct_chg": [1.0, 2.0],
            "amount": [5e10, 6e10],
            "main_net_inflow": [1e8, 2e8],
            "strength": [3.0, 4.0],
        }
    )

    got = weekly_rank(timeline)

    assert set(["week", "week_start", "week_end", "week_label"]) <= set(got.columns)
    assert got["week"].unique().tolist() == ["2026-W25"]
    assert got["week_label"].unique().tolist() == ["06/15-06/21 · 第25周"]
    assert "2026-25" not in got["week_label"].iloc[0]


def test_timeline_tolerates_missing_flow_column():
    hist = pd.DataFrame(
        {
            "date": ["2026-04-01", "2026-04-02"],
            "sector": ["证券", "电子"],
            "pct_chg": [2.0, -1.0],
            "amount": [5e10, 4e10],
        }
    )

    tl = build_rotation_timeline(hist)

    assert tl["main_net_inflow"].tolist() == [0.0, 0.0]


def test_fetch_timeline_uses_flow_latest_date_when_clock_is_ahead(monkeypatch):
    from src.pipeline import rotation_timeline as rt

    monkeypatch.setattr(
        rt.em_client,
        "industry_realtime",
        lambda: pd.DataFrame(
            {
                "sector": ["证券"],
                "amount": [10_000_000_000],
                "pct_chg": [1.2],
            }
        ),
    )
    monkeypatch.setattr(
        rt.em_client,
        "industry_fund_flow_hist",
        lambda sector: pd.DataFrame(
            {
                "sector": [sector, sector],
                "trade_date": ["2025-06-10", "2025-06-11"],
                "main_net_inflow": [100_000_000, 200_000_000],
            }
        ),
    )

    called = {}

    def fake_hist(sector, start, end):
        called["window"] = (start, end)
        if end != "20250611":
            return pd.DataFrame()
        return pd.DataFrame(
            {
                "sector": [sector, sector],
                "trade_date": ["2025-06-10", "2025-06-11"],
                "pct_chg": [0.5, 1.0],
                "amount": [1_000_000_000, 1_200_000_000],
            }
        )

    monkeypatch.setattr(rt.em_client, "industry_hist", fake_hist)

    got = rt.fetch_rotation_timeline(days=30, max_sectors=1)

    assert not got.empty
    assert called["window"][1] == "20250611"
    assert got["main_net_inflow"].sum() == 300_000_000


def test_fetch_timeline_keeps_sector_when_flow_history_fails(monkeypatch):
    from src.pipeline import rotation_timeline as rt

    monkeypatch.setattr(
        rt.em_client,
        "industry_realtime",
        lambda: pd.DataFrame(
            {
                "sector": ["证券"],
                "amount": [10_000_000_000],
                "pct_chg": [1.2],
            }
        ),
    )
    monkeypatch.setattr(
        rt.em_client,
        "industry_fund_flow_hist",
        lambda sector: (_ for _ in ()).throw(ConnectionError("remote reset")),
    )
    monkeypatch.setattr(
        rt.em_client,
        "industry_hist",
        lambda sector, start, end: pd.DataFrame(
            {
                "sector": [sector],
                "trade_date": ["2026-06-16"],
                "pct_chg": [1.0],
                "amount": [1_200_000_000],
            }
        ),
    )

    got = rt.fetch_rotation_timeline(days=30, max_sectors=1)

    assert not got.empty
    assert got.loc[0, "sector"] == "证券"
    assert got.loc[0, "main_net_inflow"] == 0.0


def test_fetch_timeline_uses_local_cached_hist_when_network_fails(
    tmp_path, monkeypatch
):
    from src.pipeline import rotation_timeline as rt

    cache_dir = tmp_path / "data" / "cache"
    hist_dir = cache_dir / "em" / "industry_hist"
    hist_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "sector": ["证券"],
            "trade_date": ["2026-06-16"],
            "pct_chg": [1.0],
            "amount": [1_200_000_000],
            "turnover": [2.0],
        }
    ).to_parquet(hist_dir / "证券_20260601_20260616.parquet", index=False)

    monkeypatch.setattr(rt.cache, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(
        rt.em_client,
        "industry_realtime",
        lambda: pd.DataFrame(
            {
                "sector": ["证券"],
                "amount": [10_000_000_000],
                "pct_chg": [1.2],
            }
        ),
    )
    monkeypatch.setattr(
        rt.em_client,
        "industry_fund_flow_hist",
        lambda sector: (_ for _ in ()).throw(ConnectionError("remote reset")),
    )
    monkeypatch.setattr(
        rt.em_client,
        "industry_hist",
        lambda sector, start, end: (_ for _ in ()).throw(ConnectionError("remote reset")),
    )

    got = rt.fetch_rotation_timeline(days=30, max_sectors=1)

    assert not got.empty
    assert got.loc[0, "sector"] == "证券"


def test_fetch_timeline_uses_network_for_uncached_sectors_when_some_cache_exists(
    tmp_path, monkeypatch
):
    from src.pipeline import rotation_timeline as rt

    cache_dir = tmp_path / "data" / "cache"
    hist_dir = cache_dir / "em" / "industry_hist"
    hist_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "sector": ["证券"],
            "trade_date": ["2026-06-16"],
            "pct_chg": [1.0],
            "amount": [1_200_000_000],
        }
    ).to_parquet(hist_dir / "证券_20260601_20260616.parquet", index=False)

    monkeypatch.setattr(rt.cache, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(
        rt.em_client,
        "industry_realtime",
        lambda: pd.DataFrame(
            {
                "sector": ["证券", "电子"],
                "amount": [10_000_000_000, 9_000_000_000],
                "pct_chg": [1.2, 0.9],
            }
        ),
    )
    monkeypatch.setattr(rt.em_client, "industry_fund_flow_hist", lambda sector: pd.DataFrame())

    def fake_hist(sector, start, end):
        if sector == "电子":
            return pd.DataFrame(
                {
                    "sector": [sector],
                    "trade_date": ["2026-06-16"],
                    "pct_chg": [0.8],
                    "amount": [1_100_000_000],
                }
            )
        return pd.DataFrame()

    monkeypatch.setattr(rt.em_client, "industry_hist", fake_hist)

    got = rt.fetch_rotation_timeline(days=30, max_sectors=2)

    assert {"证券", "电子"} <= set(got["sector"])


def test_fetch_timeline_scans_extra_candidates_until_it_has_rows(monkeypatch):
    from src.pipeline import rotation_timeline as rt

    monkeypatch.setattr(
        rt.em_client,
        "industry_realtime",
        lambda: pd.DataFrame(
            {
                "sector": ["高层行业", "证券"],
                "amount": [20_000_000_000, 10_000_000_000],
                "pct_chg": [1.2, 1.0],
            }
        ),
    )
    monkeypatch.setattr(rt.em_client, "industry_fund_flow_hist", lambda sector: pd.DataFrame())

    def fake_hist(sector, start, end):
        if sector == "高层行业":
            return pd.DataFrame()
        return pd.DataFrame(
            {
                "sector": [sector],
                "trade_date": ["2026-06-16"],
                "pct_chg": [1.0],
                "amount": [1_200_000_000],
            }
        )

    monkeypatch.setattr(rt.em_client, "industry_hist", fake_hist)

    got = rt.fetch_rotation_timeline(days=30, max_sectors=1)

    assert not got.empty
    assert got.loc[0, "sector"] == "证券"


def test_leader_changes_reports_weekly_handoff():
    weekly = pd.DataFrame(
        {
            "week": ["2026-14", "2026-14", "2026-15", "2026-15"],
            "week_start": pd.to_datetime(
                ["2026-03-30", "2026-03-30", "2026-04-06", "2026-04-06"]
            ),
            "week_end": pd.to_datetime(
                ["2026-04-05", "2026-04-05", "2026-04-12", "2026-04-12"]
            ),
            "sector": ["证券", "电子", "证券", "电子"],
            "rank": [1, 2, 2, 1],
            "strength": [8.0, 2.0, 1.0, 9.0],
        }
    )

    changes = leader_changes(weekly)

    assert changes["leaders"] == ["证券", "电子"]
    assert changes["path"] == "证券→电子"
    assert changes["segments"][0]["sector"] == "证券"
    assert changes["segments"][0]["duration_days"] == 7


def test_filter_rotation_groups_removes_vague_buckets_from_top_level():
    weekly = pd.DataFrame(
        {
            "week": ["2026-W25"] * 4,
            "week_label": ["06/15-06/21 · 第25周"] * 4,
            "sector": ["综合", "其他", "电子", "通信"],
            "rank": [1, 2, 3, 4],
            "strength": [10.0, 9.0, 8.0, 7.0],
            "main_net_inflow": [5e8, 4e8, 3e8, 2e8],
        }
    )

    filtered = filter_rotation_groups(weekly)

    assert filtered["sector"].tolist() == ["电子", "通信"]


def test_select_rotation_sectors_keeps_multiple_groups():
    weekly = pd.DataFrame(
        {
            "week": ["2026-20"] * 5 + ["2026-21"] * 5,
            "sector": ["证券", "电子", "医药", "原材料", "通信"] * 2,
            "rank": [1, 2, 3, 4, 5, 2, 1, 3, 5, 4],
            "strength": [8, 7, 6, 5, 4, 7, 9, 6, 3, 4],
            "main_net_inflow": [5e8, 4e8, 3e8, -2e8, 1e8, 2e8, 6e8, 1e8, -1e8, 1e8],
        }
    )

    selected = select_rotation_sectors(weekly, min_groups=4, max_groups=5)

    assert len(selected) >= 4
    assert "电子" in selected
    assert "证券" in selected


def test_select_rotation_sectors_skips_vague_groups():
    weekly = pd.DataFrame(
        {
            "week": ["2026-W25"] * 5,
            "sector": ["综合", "其他", "电子", "通信", "金融"],
            "rank": [1, 2, 3, 4, 5],
            "strength": [10, 9, 8, 7, 6],
            "main_net_inflow": [9e8, 8e8, 7e8, 6e8, 5e8],
        }
    )

    selected = select_rotation_sectors(weekly, min_groups=2, max_groups=4)

    assert "综合" not in selected
    assert "其他" not in selected
    assert selected[:2] == ["电子", "通信"]


def test_heatmap_flow_matrix_clips_outliers_and_uses_yi_units():
    weekly = pd.DataFrame(
        {
            "week": ["2026-20", "2026-20", "2026-21", "2026-21"],
            "sector": ["证券", "电子", "证券", "电子"],
            "rank": [1, 2, 2, 1],
            "strength": [8, 7, 6, 9],
            "main_net_inflow": [100e8, 2e8, -2e8, 3e8],
        }
    )

    matrix, limit = heatmap_flow_matrix(weekly, max_groups=2, clip_quantile=0.5)

    assert set(matrix.index) == {"证券", "电子"}
    assert limit <= 3.0
    assert matrix.to_numpy().max() <= 3.0
    assert matrix.to_numpy().min() >= -3.0


def test_heatmap_flow_matrix_uses_readable_week_labels_when_available():
    weekly = pd.DataFrame(
        {
            "week": ["2026-W25", "2026-W26"],
            "week_label": ["06/15-06/21 · 第25周", "06/22-06/28 · 第26周"],
            "sector": ["电子", "电子"],
            "rank": [1, 2],
            "strength": [8, 7],
            "main_net_inflow": [2e8, 3e8],
        }
    )

    matrix, _ = heatmap_flow_matrix(weekly, max_groups=1)

    assert matrix.columns.tolist() == ["06/15-06/21 · 第25周", "06/22-06/28 · 第26周"]


def test_relative_flow_heatmap_shows_relative_winners_when_all_absolute_flow_out():
    weekly = pd.DataFrame(
        {
            "week": ["2026-W25"] * 3,
            "week_label": ["06/15-06/21 · 第25周"] * 3,
            "sector": ["金融", "电子", "医药"],
            "rank": [1, 2, 3],
            "strength": [8, 7, 6],
            "main_net_inflow": [-12e8, -3e8, -8e8],
        }
    )

    matrix, limit = relative_flow_heatmap_matrix(weekly, max_groups=3)

    assert limit == 100.0
    assert matrix.loc["电子", "06/15-06/21 · 第25周"] > 0
    assert matrix.loc["金融", "06/15-06/21 · 第25周"] < 0
