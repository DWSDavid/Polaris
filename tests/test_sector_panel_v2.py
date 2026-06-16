import pandas as pd

from src.pipeline.sector_panel_v2 import build_sector_panel_v2


def test_panel_schema_and_state_from_real_features():
    industry = pd.DataFrame(
        {
            "sector": ["电力设备", "银行"],
            "pct_chg": [2.8, -0.4],
            "amount": [9e10, 2e10],
            "main_net_inflow": [8e9, -2e8],
            "up_count": [80, 15],
            "down_count": [20, 25],
            "leading_stock": ["阳光电源", "招商银行"],
        }
    )
    flow_5d = pd.DataFrame(
        {
            "sector": ["电力设备", "银行"],
            "main_net_inflow": [9e9, -1e9],
        }
    )
    flow_10d = pd.DataFrame(
        {
            "sector": ["电力设备", "银行"],
            "main_net_inflow": [12.3e9, 4e8],
        }
    )
    histories = {
        "电力设备": pd.DataFrame(
            {
                "pct_chg": [-1.0, 0.4, 1.0, 1.3, 1.5],
                "amount": [3e10, 4e10, 5e10, 7e10, 9e10],
                "main_net_inflow": [2e9, 4e9, 6e9, 8e9, 8.2e9],
            }
        ),
        "银行": pd.DataFrame(
            {
                "pct_chg": [1.0, -0.2, -0.4],
                "amount": [2e10, 2.1e10, 2e10],
                "main_net_inflow": [2e8, 1e8, -2e8],
            }
        ),
    }
    leaders = pd.DataFrame(
        {
            "sector": ["电力设备", "电力设备", "银行"],
            "name": ["宁德时代", "阳光电源", "招商银行"],
            "rank": [1, 2, 1],
            "amount": [8e9, 7e9, 1e9],
        }
    )

    panel = build_sector_panel_v2(
        industry_realtime=industry,
        flow_5d=flow_5d,
        flow_10d=flow_10d,
        histories=histories,
        leaders=leaders,
    )

    need = {
        "pct_chg",
        "amount",
        "main_net_inflow",
        "inflow_5d",
        "inflow_10d",
        "trend_days",
        "turning_point",
        "top_leaders",
        "state",
        "strength",
        "strength_rank",
    }
    assert need <= set(panel.columns)
    power = panel[panel["sector"] == "电力设备"].iloc[0]
    assert power["inflow_10d"] == 12.3e9
    assert power["trend_days"] == 3
    assert power["top_leaders"] == "宁德时代、阳光电源"
    assert power["state"] == "主升扩散"
    bank = panel[panel["sector"] == "银行"].iloc[0]
    assert bank["turning_point"] is True


def test_top_leaders_falls_back_to_realtime_leading_stock_without_leader_frame():
    industry = pd.DataFrame(
        {
            "sector": ["通信线缆及配套"],
            "pct_chg": [7.0],
            "amount": [5e10],
            "main_net_inflow": [3e9],
            "up_count": [13],
            "down_count": [0],
            "leading_stock": ["永鼎股份"],
        }
    )

    panel = build_sector_panel_v2(
        industry_realtime=industry,
        flow_5d=pd.DataFrame({"sector": ["通信线缆及配套"], "main_net_inflow": [1e9]}),
        flow_10d=pd.DataFrame({"sector": ["通信线缆及配套"], "main_net_inflow": [2e9]}),
    )

    assert panel.loc[0, "top_leaders"] == "永鼎股份"
