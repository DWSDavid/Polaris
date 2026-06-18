import pandas as pd

from src.compute.hot_focus import build_hot_dragon_focus


def test_hot_dragon_focus_prioritizes_hot_lhb_positive_net_buy():
    hot = pd.DataFrame(
        {
            "hot_rank": [1, 5, 8],
            "code": ["000636", "600487", "000010"],
            "market_code": ["SZ000636", "SH600487", "SZ000010"],
            "name": ["风华高科", "亨通光电", "*ST美丽"],
            "latest_price": [70.61, 107.5, 2.43],
            "pct_chg": [8.58, 8.28, 5.19],
        }
    )
    dragon = pd.DataFrame(
        {
            "code": ["600487", "600487"],
            "name": ["亨通光电", "亨通光电"],
            "net_buy": [9e7, 1e7],
            "reason": ["日涨幅偏离值达到7%的前5只证券", "机构专用买入"],
            "trade_date": ["2026-06-16", "2026-06-16"],
        }
    )

    focus = build_hot_dragon_focus(hot, dragon, top_n=100)

    assert "*ST美丽" not in set(focus["name"])
    leader = focus.iloc[0]
    assert leader["code"] == "600487"
    assert leader["dragon_tiger_on_list"] is True
    assert leader["dragon_tiger_net_buy"] == 1e8
    assert leader["dragon_tiger_latest_date"] == "2026-06-16"
    assert "热度前5" in leader["focus_reason"]
    assert "龙虎榜净买" in leader["focus_reason"]


def test_hot_dragon_focus_handles_hot_only_rows():
    hot = pd.DataFrame(
        {
            "hot_rank": [1],
            "code": ["000636"],
            "market_code": ["SZ000636"],
            "name": ["风华高科"],
            "latest_price": [70.61],
            "pct_chg": [8.58],
        }
    )

    focus = build_hot_dragon_focus(hot, pd.DataFrame(), top_n=100)

    assert focus.loc[0, "dragon_tiger_on_list"] is False
    assert focus.loc[0, "dragon_tiger_net_buy"] == 0
    assert focus.loc[0, "focus_reason"] == "热度前1，先观察是否有资金行为确认"


def test_hot_dragon_focus_adds_trend_metrics_from_history():
    hot = pd.DataFrame(
        {
            "hot_rank": [1],
            "code": ["000636"],
            "market_code": ["SZ000636"],
            "name": ["风华高科"],
            "latest_price": [70.61],
            "pct_chg": [8.58],
        }
    )
    history = pd.DataFrame(
        {
            "close": list(range(10, 35)),
            "pct": [0.2] * 22 + [1.1, 2.2, 3.3],
        }
    )

    focus = build_hot_dragon_focus(
        hot,
        pd.DataFrame(),
        top_n=100,
        histories={"000636": history},
    )

    assert focus.loc[0, "consecutive_up_days"] == 25
    assert focus.loc[0, "trend_days"] == 25
    assert focus.loc[0, "midterm_trend"] == 1
    assert focus.loc[0, "return_20d"] > 0
