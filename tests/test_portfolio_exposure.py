import pandas as pd

from src.compute.portfolio_exposure import (
    build_portfolio_exposure,
    portfolio_offset_report,
)


def _stock_panel():
    return pd.DataFrame(
        {
            "code": ["000001", "600000", "300750"],
            "symbol": ["SZ000001", "SH600000", "SZ300750"],
            "name": ["平安银行", "浦发银行", "宁德时代"],
            "sector": ["金融", "金融", "信息技术"],
        }
    )


def _diagnostics():
    return pd.DataFrame(
        {
            "sector": ["金融", "信息技术"],
            "fund_flow_yi": [-1.2, 2.4],
            "money_direction": ["净流出", "净流入"],
            "trend_label": ["中期下行", "1-3周上行"],
            "split_label": ["明显分化", "温和分化"],
        }
    )


def test_build_portfolio_exposure_maps_holdings_to_sector():
    holdings = [
        {"code": "600000", "name": "浦发银行", "shares": 10.0, "cost": 8.0},
        {"code": "300750", "name": "宁德时代", "shares": 2.0, "cost": 180.0},
    ]

    exposure = build_portfolio_exposure(holdings, _stock_panel(), _diagnostics())

    finance = exposure[exposure["sector"] == "金融"].iloc[0]
    growth = exposure[exposure["sector"] == "信息技术"].iloc[0]
    assert finance["market_value_wan"] == 80.0
    assert growth["market_value_wan"] == 360.0
    assert round(growth["weight"], 2) == 0.82
    assert growth["fund_flow_yi"] == 2.4


def test_portfolio_offset_report_flags_opposite_money_directions():
    holdings = [
        {"code": "600000", "name": "浦发银行", "shares": 10.0, "cost": 20.0},
        {"code": "300750", "name": "宁德时代", "shares": 1.0, "cost": 200.0},
    ]
    exposure = build_portfolio_exposure(holdings, _stock_panel(), _diagnostics())

    report = portfolio_offset_report(exposure)

    assert report["offset_level"] == "high"
    assert "金融" in report["message"]
    assert "信息技术" in report["message"]


def test_portfolio_offset_report_prefers_negative_correlation_pairs():
    exposure = pd.DataFrame(
        {
            "sector": ["证券", "电子"],
            "market_value_wan": [100.0, 100.0],
            "weight": [0.5, 0.5],
            "fund_flow_yi": [1.0, 1.0],
            "money_direction": ["净流入", "净流入"],
            "trend_label": ["主升扩散", "主升扩散"],
            "split_label": ["正常", "正常"],
        }
    )
    corr = pd.DataFrame(
        [[1.0, -0.8], [-0.8, 1.0]],
        index=["证券", "电子"],
        columns=["证券", "电子"],
    )

    report = portfolio_offset_report(exposure, corr=corr)

    assert report["offset_level"] == "high"
    assert report["hedge_score"] > 0.5
    assert ["证券", "电子"] in report["hedge_pairs"] or ["电子", "证券"] in report["hedge_pairs"]
