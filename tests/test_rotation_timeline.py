import pandas as pd
import pytest

from src.pipeline.rotation_timeline import (
    build_rotation_timeline,
    leader_changes,
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
            "sector": ["证券", "电子", "证券", "电子"],
            "rank": [1, 2, 2, 1],
            "strength": [8.0, 2.0, 1.0, 9.0],
        }
    )

    changes = leader_changes(weekly)

    assert changes["leaders"] == ["证券", "电子"]
    assert changes["path"] == "证券→电子"
    assert changes["segments"][0]["sector"] == "证券"
