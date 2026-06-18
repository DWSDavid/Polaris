import pandas as pd

from src.compute.stock_decision import build_stock_facts, evaluate_stock_setup


def _daily(closes: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2026-03-01", periods=len(closes), freq="D")
    frame = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "close": closes,
            "amount": [1_000_000_000 + i * 10_000_000 for i in range(len(closes))],
        }
    )
    frame["pct"] = pd.Series(closes).pct_change().fillna(0) * 100
    return frame


def test_stock_setup_marks_entry_when_stock_and_sector_confirm_each_other():
    closes = [10 + i * 0.08 for i in range(70)]
    facts = build_stock_facts(
        stock={
            "code": "601688",
            "symbol": "SH601688",
            "name": "华泰证券",
            "latest_price": closes[-1],
            "pct_chg": 2.4,
            "amount": 2_800_000_000,
            "volume_ratio": 1.6,
            "turnover_rate": 2.1,
            "pe_ttm": 12.5,
            "pb": 1.2,
            "total_mv": 180_000_000_000,
        },
        daily=_daily(closes),
        flow=pd.DataFrame(
            {
                "日期": pd.date_range("2026-05-01", periods=10).strftime("%Y-%m-%d"),
                "主力净流入-净额": [20_000_000] * 10,
            }
        ),
        sector={
            "sector": "证券",
            "group": "金融",
            "state": "主升扩散",
            "trend_days": 6,
            "inflow_10d": 3_000_000_000,
            "main_net_inflow": 500_000_000,
            "pct_chg": 1.2,
            "turning_point": False,
            "top_leaders": "华泰证券、东方财富",
        },
    )

    decision = evaluate_stock_setup(facts)

    assert facts["above_ma20"] is True
    assert facts["above_ma60"] is True
    assert facts["stock_inflow_5d"] > 0
    assert decision["stance"] == "适合观察入场"
    assert "行业主线支持" in decision["reasons"]
    assert "个股中期结构向上" in decision["reasons"]


def test_stock_setup_marks_exit_when_holding_breaks_structure_and_drawdown_limit():
    closes = [20 - i * 0.11 for i in range(70)]
    facts = build_stock_facts(
        stock={
            "code": "601688",
            "symbol": "SH601688",
            "name": "华泰证券",
            "latest_price": closes[-1],
            "pct_chg": -3.2,
            "amount": 1_600_000_000,
            "volume_ratio": 1.3,
            "turnover_rate": 2.0,
        },
        daily=_daily(closes),
        flow=pd.DataFrame(
            {
                "日期": pd.date_range("2026-05-01", periods=10).strftime("%Y-%m-%d"),
                "主力净流入-净额": [-30_000_000] * 10,
            }
        ),
        sector={
            "sector": "证券",
            "group": "金融",
            "state": "分歧退潮",
            "trend_days": -4,
            "inflow_10d": -1_000_000_000,
            "main_net_inflow": -300_000_000,
            "pct_chg": -1.0,
            "turning_point": True,
        },
        holding={"cost": 18.5, "shares": 1000},
    )

    decision = evaluate_stock_setup(facts)

    assert facts["holding_return"] <= -0.10
    assert decision["stance"] == "减仓/退出观察"
    assert "跌破60日均线" in decision["risk_flags"]
    assert "持仓回撤超过10%" in decision["risk_flags"]


def test_stock_setup_warns_when_price_is_too_high_even_if_trend_is_strong():
    closes = [10] * 30 + [10 + i * 0.55 for i in range(40)]
    facts = build_stock_facts(
        stock={"code": "300750", "symbol": "SZ300750", "name": "宁德时代", "latest_price": closes[-1], "volume_ratio": 3.8},
        daily=_daily(closes),
        flow=pd.DataFrame({"主力净流入-净额": [100_000_000] * 5}),
        sector={"sector": "电力设备", "state": "高位加速", "inflow_10d": 2_000_000_000},
    )

    decision = evaluate_stock_setup(facts)

    assert facts["position_in_box"] >= 0.9
    assert "箱体位置过高" in decision["risk_flags"]
    assert decision["stance"] != "适合观察入场"


def test_missing_daily_history_does_not_fake_a_ma60_breakdown():
    facts = build_stock_facts(
        stock={"code": "601688", "symbol": "SH601688", "name": "华泰证券", "latest_price": 19.7},
        daily=pd.DataFrame(),
        flow=pd.DataFrame(),
        sector={"sector": "证券", "state": "主升扩散", "inflow_10d": 2_000_000_000},
    )

    decision = evaluate_stock_setup(facts)

    assert facts["above_ma60"] is None
    assert "跌破60日均线" not in decision["risk_flags"]


def test_stock_facts_include_bull_trap_pattern_when_history_loaded():
    closes = [30 - i * 0.18 for i in range(65)] + [18.7, 19.4, 20.1]
    daily = _daily(closes)
    daily["main_net_inflow"] = [-20_000_000] * 65 + [-80_000_000, -60_000_000, -50_000_000]

    facts = build_stock_facts(
        stock={"code": "601688", "symbol": "SH601688", "name": "华泰证券", "latest_price": closes[-1], "volume_ratio": 1.8},
        daily=daily,
        flow=pd.DataFrame(),
        sector={"sector": "证券", "state": "龙头孤立", "inflow_10d": -1_000_000_000},
    )
    decision = evaluate_stock_setup(facts)

    assert facts["pattern_risk"]["label"] == "疑似诱多风险"
    assert facts["historical_trap"]["sample_count"] >= 0
    assert "疑似诱多风险" in decision["risk_flags"]
