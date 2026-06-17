import pandas as pd

from src.data.sector_groups import (
    SECTOR_GROUP_DESCRIPTIONS,
    aggregate_to_groups,
    aggregate_timeline_to_groups,
    map_to_group,
)
from src.pipeline.sector_panel_v2 import build_sector_panel_v2


def test_fine_sector_maps_to_group():
    assert map_to_group("钨") == "原材料"
    assert map_to_group("其他电子Ⅲ") == "电子"
    assert map_to_group("证券") in ("金融", "非银金融")
    assert map_to_group("数字芯片设计") == "半导体"
    assert map_to_group("自动化设备") == "机械/电力设备"
    assert map_to_group("交通运输") == "交通运输"
    assert map_to_group("建筑装饰") == "建筑建材"
    assert map_to_group("环保设备Ⅲ") == "环保"
    assert map_to_group("农林牧渔") == "农业"
    assert map_to_group("纺织服饰") == "轻工纺服"
    assert map_to_group("调味发酵品Ⅲ") == "消费"
    assert map_to_group("光伏发电") == "公用事业"
    assert map_to_group("航空机场") == "交通运输"
    assert map_to_group("水务及水治理") == "环保"
    assert map_to_group("地面兵装Ⅲ") == "军工"
    assert map_to_group("轮胎轮毂") == "汽车"
    assert map_to_group("电视广播Ⅲ") == "传媒"
    assert map_to_group("商业物业经营") == "地产"
    assert map_to_group("医院") == "医药"
    assert map_to_group("啤酒") == "消费"
    assert map_to_group("高速公路") == "交通运输"
    assert map_to_group("金融控股") == "金融"


def test_sector_group_descriptions_explain_vague_comprehensive_bucket():
    assert "综合" in SECTOR_GROUP_DESCRIPTIONS
    assert "不参与主线领跑" in SECTOR_GROUP_DESCRIPTIONS["综合"]
    assert "钨" in SECTOR_GROUP_DESCRIPTIONS["原材料"]


def test_aggregate_rolls_up():
    fine = pd.DataFrame(
        {
            "sector": ["钨", "稀土", "半导体"],
            "group": ["原材料", "原材料", "电子"],
            "amount": [8e8, 1e9, 5e10],
            "main_net_inflow": [2e8, 3e8, -1e8],
            "stock_count": [4, 6, 120],
        }
    )

    g = aggregate_to_groups(fine)
    mat = g[g["group"] == "原材料"].iloc[0]

    assert mat["amount"] == 8e8 + 1e9
    assert mat["stock_count"] == 10
    assert "钨" in mat["children"] and "稀土" in mat["children"]


def test_aggregate_weighted_fields_downweight_thin_sectors():
    fine = pd.DataFrame(
        {
            "sector": ["钨", "有色金属"],
            "amount": [1e8, 9e8],
            "main_net_inflow": [1e7, 2e7],
            "stock_count": [2, 80],
            "diffusion": [1.0, 0.2],
            "pct_chg": [10.0, 1.0],
        }
    )

    got = aggregate_to_groups(fine)
    row = got[got["group"] == "原材料"].iloc[0]

    assert row["diffusion"] < 0.5
    assert row["pct_chg"] < 3.0
    assert row["sample_note"] == "样本充足"


def test_sector_panel_keeps_fine_sector_and_group_for_drilldown():
    panel = build_sector_panel_v2(
        industry_realtime=pd.DataFrame(
            {
                "sector": ["钨", "稀土"],
                "pct_chg": [5.0, 3.0],
                "amount": [1e9, 2e9],
                "main_net_inflow": [2e8, 3e8],
                "up_count": [3, 5],
                "down_count": [1, 1],
                "leading_stock": ["厦门钨业", "盛和资源"],
            }
        ),
        flow_5d=pd.DataFrame({"sector": ["钨", "稀土"], "main_net_inflow": [1e8, 2e8]}),
        flow_10d=pd.DataFrame({"sector": ["钨", "稀土"], "main_net_inflow": [2e8, 3e8]}),
    )

    assert set(panel["sector"]) == {"钨", "稀土"}
    assert panel["group"].eq("原材料").all()
    group_panel = aggregate_to_groups(panel)
    assert group_panel["sector"].tolist() == ["原材料"]


def test_aggregate_timeline_rolls_up_each_date_separately():
    timeline = pd.DataFrame(
        {
            "date": ["2026-06-01", "2026-06-01", "2026-06-02", "2026-06-02"],
            "sector": ["钨", "半导体", "稀土", "其他电子Ⅲ"],
            "pct_chg": [5.0, 1.0, 3.0, 2.0],
            "amount": [1e9, 10e9, 2e9, 8e9],
            "main_net_inflow": [2e8, -1e8, 3e8, 1e8],
        }
    )

    got = aggregate_timeline_to_groups(timeline)

    assert set(got["sector"]) == {"原材料", "半导体", "电子"}
    assert got[(got["date"] == "2026-06-01") & (got["sector"] == "原材料")].iloc[0]["amount"] == 1e9
    assert "钨" in got[(got["date"] == "2026-06-01") & (got["sector"] == "原材料")].iloc[0]["children"]
