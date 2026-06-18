import pandas as pd

from src.compute.pattern_risk import (
    detect_bull_trap_risk,
    historical_trap_report,
)


def _frame(closes: list[float], flow: list[float] | None = None) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "trade_date": pd.date_range("2026-01-01", periods=len(closes)).strftime("%Y%m%d"),
            "close": closes,
            "amount": [1_000_000_000] * len(closes),
        }
    )
    frame["pct_chg"] = pd.Series(closes).pct_change().fillna(0) * 100
    if flow is not None:
        frame["main_net_inflow"] = flow
    return frame


def test_detects_bull_trap_after_downtrend_bounce_with_flow_divergence():
    closes = [30 - i * 0.18 for i in range(65)] + [18.7, 19.4, 20.1]
    flow = [-20_000_000] * 65 + [-80_000_000, -60_000_000, -50_000_000]

    report = detect_bull_trap_risk(_frame(closes, flow))

    assert report["label"] == "疑似诱多风险"
    assert report["risk_score"] >= 0.7
    assert "中期仍在60日线下" in report["reasons"]
    assert "反弹资金背离" in report["reasons"]


def test_does_not_flag_clean_breakout_with_positive_funding():
    closes = [10 + i * 0.08 for i in range(68)]
    flow = [20_000_000] * 68

    report = detect_bull_trap_risk(_frame(closes, flow))

    assert report["label"] == "结构未显示诱多"
    assert report["risk_score"] < 0.4


def test_historical_trap_report_summarizes_forward_failure_rate():
    first_trap = [30 - i * 0.2 for i in range(65)] + [17.4, 18.0, 18.6, 17.5, 17.0, 16.5]
    second_trap = [28 - i * 0.16 for i in range(65)] + [18.2, 18.8, 19.5, 18.3, 17.7, 17.2]
    history = _frame(first_trap + second_trap, [-30_000_000] * (len(first_trap) + len(second_trap)))

    report = historical_trap_report(history, horizons=(3, 5), min_score=0.6)

    assert report["sample_count"] >= 2
    assert report["median_forward_return_5d"] < 0
    assert report["win_rate_5d"] < 0.5
    assert "诱多" in report["summary"]
