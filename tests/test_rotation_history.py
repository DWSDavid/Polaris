import pandas as pd

from src.compute.rotation_history import (
    build_stock_history,
    build_sector_history,
    summarize_sector_track,
)


def _stocks():
    return pd.DataFrame(
        {
            "sector": ["信息技术", "信息技术", "金融"],
            "symbol": ["SZ000001", "SZ000002", "SH600000"],
            "name": ["A", "B", "C"],
            "rank": [1, 4, 1],
        }
    )


def _daily():
    dates = pd.date_range("2026-06-01", periods=6).strftime("%Y%m%d")
    return {
        "SZ000001": pd.DataFrame(
            {
                "trade_date": dates,
                "close": [10, 10.3, 10.6, 10.8, 11.1, 11.4],
                "pct_chg": [1.0, 2.0, 1.5, -0.2, 2.2, 1.8],
                "amount": [100, 120, 130, 110, 150, 160],
            }
        ),
        "SZ000002": pd.DataFrame(
            {
                "trade_date": dates,
                "close": [8, 8.1, 8.0, 8.2, 8.3, 8.4],
                "pct_chg": [0.5, -0.5, -1.0, -0.6, 0.8, 0.6],
                "amount": [40, 45, 42, 43, 44, 46],
            }
        ),
        "SH600000": pd.DataFrame(
            {
                "trade_date": dates,
                "close": [7, 6.9, 6.8, 6.7, 6.6, 6.5],
                "pct_chg": [-1.0, -1.2, -0.8, -0.6, -0.5, -0.4],
                "amount": [80, 75, 70, 65, 60, 55],
            }
        ),
    }


def test_build_sector_history_aggregates_by_trade_date():
    history = build_sector_history(_stocks(), _daily())

    first = history[
        (history["sector"] == "信息技术") & (history["trade_date"] == "20260601")
    ].iloc[0]
    assert first["stock_count"] == 2
    assert first["positive_count"] == 2
    assert first["diffusion"] == 1.0
    assert first["amount"] == 140
    assert first["leader_amount"] == 100
    assert round(first["leader_contrib"], 2) == 0.71


def test_summarize_sector_track_reports_windows_and_streaks():
    history = build_sector_history(_stocks(), _daily())

    summary = summarize_sector_track(history, short_window=3, mid_window=6)
    tech = summary[summary["sector"] == "信息技术"].iloc[0]
    finance = summary[summary["sector"] == "金融"].iloc[0]

    assert tech["fund_flow_3d"] > 0
    assert tech["positive_days_6d"] == 5
    assert tech["current_positive_streak"] == 2
    assert tech["track_label"] == "资金延续流入"
    assert finance["track_label"] == "持续承压"


def test_build_stock_history_keeps_recent_daily_series_with_metadata():
    history = build_stock_history(_stocks(), _daily())

    stock = history[history["symbol"] == "SZ000001"]
    assert len(stock) == 6
    assert {
        "sector",
        "symbol",
        "name",
        "rank",
        "trade_date",
        "close",
        "pct_chg",
    } <= set(stock.columns)
    assert stock.iloc[-1]["name"] == "A"
    assert stock.iloc[-1]["close"] == 11.4
