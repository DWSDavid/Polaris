from src.compute.exit_signal import exit_flag


def test_exit_flag_on_turning_point():
    result = exit_flag({"sector": "证券", "turning_point": True})

    assert result["exit"] is True
    assert "拐点" in result["reason"]


def test_exit_flag_on_overdue_trend_days():
    result = exit_flag({"sector": "证券", "trend_days": 9}, max_trend_days=7)

    assert result["exit"] is True
    assert "超期" in result["reason"]


def test_exit_flag_on_price_up_but_fund_weakens():
    result = exit_flag({"sector": "证券", "pct_chg": 2.1, "main_net_inflow": -1e8})

    assert result["exit"] is True
    assert "量价背离" in result["reason"]
