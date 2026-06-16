import pandas as pd

from src.compute import linkage_stats as ls


def test_detect_leader_events():
    daily = pd.DataFrame(
        {
            "trade_date": ["20260601", "20260602", "20260603"],
            "pct_chg": [1.0, 5.2, 2.0],
            "volume_ratio": [1.0, 2.1, 1.1],
        }
    )

    events = ls.detect_leader_events(daily, pct_threshold=3.0, volume_threshold=1.5)

    assert list(events["trade_date"]) == ["20260602"]


def test_forward_excess_returns():
    sector_daily = pd.DataFrame(
        {
            "trade_date": ["20260601", "20260602", "20260603", "20260604"],
            "close": [100.0, 102.0, 105.0, 106.0],
        }
    )
    benchmark_daily = pd.DataFrame(
        {
            "trade_date": ["20260601", "20260602", "20260603", "20260604"],
            "close": [100.0, 101.0, 102.0, 103.0],
        }
    )

    result = ls.forward_excess_returns(
        event_dates=["20260602"],
        sector_daily=sector_daily,
        benchmark_daily=benchmark_daily,
        horizons=[1, 2],
    )

    assert abs(result.loc[0, "t1_excess"] - ((105 / 102) - (102 / 101))) < 1e-9
    assert "t2_excess" in result.columns


def test_summarize_linkage_stats():
    events = pd.DataFrame(
        {
            "event_date": ["20260602", "20260610"],
            "t1_excess": [0.02, -0.01],
            "t3_excess": [0.05, 0.03],
        }
    )

    summary = ls.summarize_linkage_stats(events, horizons=[1, 3])

    assert summary["event_count"] == 2
    assert summary["t1_win_rate"] == 0.5
    assert summary["t3_avg_excess"] == 0.04


def test_leader_linkage_report_classifies_confirmed_linkage():
    leader_daily = pd.DataFrame(
        {
            "trade_date": ["20260601", "20260602", "20260603", "20260604", "20260605", "20260606"],
            "pct_chg": [1.0, 5.5, 0.2, 4.2, 0.1, 0.2],
            "volume_ratio": [1.0, 2.0, 1.1, 1.8, 1.0, 1.0],
        }
    )
    sector_daily = pd.DataFrame(
        {
            "trade_date": ["20260601", "20260602", "20260603", "20260604", "20260605", "20260606"],
            "close": [100.0, 101.0, 103.0, 104.0, 107.0, 108.0],
        }
    )

    report = ls.leader_linkage_report(
        leader_daily,
        sector_daily,
        horizons=[1, 2],
        pct_threshold=3.0,
        volume_threshold=1.5,
    )

    assert report["event_count"] == 2
    assert report["t1_win_rate"] >= 0.5
    assert report["label"] == "联动确认"
    assert "龙头放量后" in report["summary"]


def test_leader_linkage_report_handles_no_events():
    report = ls.leader_linkage_report(
        pd.DataFrame({"trade_date": ["20260601"], "pct_chg": [1.0], "volume_ratio": [1.0]}),
        pd.DataFrame({"trade_date": ["20260601"], "close": [100.0]}),
    )

    assert report["event_count"] == 0
    assert report["label"] == "样本不足"
