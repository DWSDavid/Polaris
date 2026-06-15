import pandas as pd

from src.compute.market_intelligence import (
    build_ai_context,
    hedge_alerts,
    sector_diagnostics,
)


def _sample_panel():
    return pd.DataFrame(
        {
            "state": ["主升扩散", "分歧退潮", "龙头孤立"],
            "strength": [2.1, -1.2, 0.4],
            "strength_rank": [0.95, 0.15, 0.55],
            "fund_flow": [180_000_000.0, -120_000_000.0, 20_000_000.0],
            "diffusion": [0.72, 0.25, 0.35],
            "leader_contrib": [0.42, 0.78, 0.82],
            "trend20": [1, -1, 1],
            "consecutive_up": [6, 0, 3],
            "top_leaders": ["A、B、C", "D、E、F", "G、H、I"],
            "signals_confirmed": [True, True, True],
        },
        index=["信息技术", "金融", "主要消费"],
    )


def _sample_stocks():
    return pd.DataFrame(
        {
            "sector": ["信息技术", "信息技术", "信息技术", "金融", "金融"],
            "rank": [1, 2, 5, 1, 4],
            "symbol": ["SZ000001", "SZ000002", "SZ000003", "SH600000", "SH600001"],
            "name": ["A", "B", "C", "D", "E"],
            "pct_chg": [5.0, 2.0, -1.0, -3.0, 1.0],
            "amount": [
                10_000_000.0,
                8_000_000.0,
                4_000_000.0,
                9_000_000.0,
                2_000_000.0,
            ],
            "volume_ratio": [1.8, 1.3, 0.8, 1.2, 0.9],
            "trend20": [1, 1, -1, -1, 1],
            "consecutive_up": [5, 3, 0, 0, 2],
            "stock_role": ["市值龙头", "市值龙头", "中军", "市值龙头", "中军"],
            "pe_ttm": [42.0, 38.0, 30.0, 7.0, 9.0],
            "pb": [4.0, 3.5, 2.8, 0.7, 0.8],
        }
    )


def test_sector_diagnostics_explains_money_trend_and_split():
    diagnostics = sector_diagnostics(_sample_panel(), _sample_stocks())

    top = diagnostics.iloc[0]
    assert top["sector"] == "信息技术"
    assert top["fund_flow_yi"] == 1.8
    assert top["money_direction"] == "净流入"
    assert top["trend_label"] == "1-3周上行"
    assert top["split_label"] == "温和分化"
    assert top["valuation_label"] == "高估值"
    assert "A" in top["leader_line"]
    assert "扩散72%" in top["brief"]


def test_hedge_alerts_identifies_old_vs_growth_offset():
    diagnostics = sector_diagnostics(_sample_panel(), _sample_stocks())

    alerts = hedge_alerts(diagnostics)

    assert len(alerts) == 1
    assert alerts[0]["growth_sector"] == "信息技术"
    assert alerts[0]["old_economy_sector"] == "金融"
    assert alerts[0]["offset_risk"] == "high"


def test_build_ai_context_is_grounded_in_numbers():
    diagnostics = sector_diagnostics(_sample_panel(), _sample_stocks())

    context = build_ai_context(diagnostics, hedge_alerts(diagnostics))

    assert "信息技术" in context
    assert "+1.8亿" in context
    assert "扩散72%" in context
    assert "对冲" in context
