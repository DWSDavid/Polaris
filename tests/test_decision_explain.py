import pandas as pd

from src.compute import decision_explain as de


def test_explain_sector_state_returns_action_and_risk():
    explanation = de.explain_sector_state(
        state="高位加速",
        diffusion=0.72,
        leader_contrib=0.68,
        fund_flow=1.0,
    )

    assert explanation["risk_level"] == "high"
    assert "回撤" in explanation["watch_points"]
    assert "追高" in explanation["action_hint"]


def test_classify_stock_roles():
    stocks = pd.DataFrame(
        {
            "rank": [1, 4, 9],
            "pct_chg": [4.2, 1.0, -1.0],
            "volume_ratio": [2.1, 1.1, 0.8],
        }
    )

    roles = de.classify_stock_roles(stocks)

    assert list(roles["stock_role"]) == ["市值龙头", "中军", "跟随观察"]
    assert roles.loc[0, "momentum_flag"] is True


def test_enrich_sector_and_stock_explanations():
    sector_panel = pd.DataFrame(
        {
            "state": ["龙头孤立"],
            "diffusion": [0.25],
            "leader_contrib": [0.8],
            "fund_flow": [1.0],
        },
        index=["证券"],
    )
    stock_panel = pd.DataFrame(
        {"sector": ["证券"], "rank": [1], "pct_chg": [3.2], "volume_ratio": [1.8]}
    )

    sectors, stocks = de.enrich_decision_explanations(sector_panel, stock_panel)

    assert sectors.loc["证券", "risk_level"] == "medium"
    assert stocks.loc[0, "stock_role"] == "市值龙头"
