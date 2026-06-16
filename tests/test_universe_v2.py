import pandas as pd

from src.data.universe_v2 import add_momentum_leaders, filter_noise, pick_leaders


def test_filter_noise():
    df = pd.DataFrame(
        {
            "name": ["银行A", "ST差", "次新B", "小盘C", "龙头D", "*ST坏"],
            "is_st": [False, True, False, False, False, True],
            "list_days": [2000, 2000, 120, 2000, 3000, 3000],
            "total_mv": [5e10, 1e10, 2e10, 8e8, 9e10, 1e11],
            "amount": [3e9, 1e9, 2e9, 1e7, 5e9, 4e9],
        }
    )

    out = filter_noise(df, min_mv=2e9, min_amount=1e8, min_list_days=365)

    assert set(out["name"]) == {"银行A", "龙头D"}


def test_filter_noise_detects_st_from_name_when_flag_missing():
    df = pd.DataFrame(
        {
            "name": ["正常A", "ST差", "*ST坏"],
            "list_days": [1000, 1000, 1000],
            "total_mv": [5e10, 5e10, 5e10],
            "amount": [1e9, 1e9, 1e9],
        }
    )

    out = filter_noise(df)

    assert list(out["name"]) == ["正常A"]


def test_pick_leaders_blends_score():
    df = pd.DataFrame(
        {
            "sector": ["银行", "银行"],
            "code": ["600000", "000001"],
            "name": ["大慢", "小热"],
            "total_mv": [9e10, 1e10],
            "amount": [1e9, 8e9],
            "turnover": [0.5, 9.0],
        }
    )

    out = pick_leaders(df, top_n=2)

    assert set(out["name"]) == {"大慢", "小热"}
    assert "leader_score" in out.columns
    assert out["leader_type"].eq("market_cap").all()
    assert out["rank"].tolist() == [1, 2]


def test_add_momentum_leaders_appends_manual_list_without_duplicates():
    base = pd.DataFrame(
        {
            "sector": ["电力设备"],
            "code": ["300750"],
            "name": ["宁德时代"],
            "leader_type": ["market_cap"],
        }
    )
    manual = [
        {"sector": "电力设备", "code": "300750", "name": "宁德时代"},
        {"sector": "电力设备", "code": "300274", "name": "阳光电源"},
    ]

    out = add_momentum_leaders(base, manual)

    assert len(out) == 2
    row = out[out["code"] == "300274"].iloc[0]
    assert row["leader_type"] == "momentum"
