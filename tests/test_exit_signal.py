from src.compute.exit_signal import exit_flag, turning_point_score


def test_small_pullback_in_uptrend_is_noise():
    row = {
        "pullback_from_high": 0.08,
        "midterm_trend": 1,
        "price_above_ma60": True,
        "cum_inflow_20d": 5e8,
        "below_box_low": False,
    }

    assert exit_flag(row)["exit"] is False


def test_structural_break_triggers_exit():
    row = {
        "pullback_from_high": 0.15,
        "midterm_trend": -1,
        "price_above_ma60": False,
        "cum_inflow_20d": -6e8,
        "below_box_low": True,
    }

    assert exit_flag(row)["exit"] is True


def test_exit_flag_on_turning_point():
    result = exit_flag({"sector": "证券", "turning_point": True})

    assert result["exit"] is False
    assert result["level"] == "watch"
    assert "拐点" in result["reason"]


def test_exit_flag_on_overdue_trend_days():
    result = exit_flag({"sector": "证券", "trend_days": 9}, max_trend_days=7)

    assert result["exit"] is False
    assert result["level"] == "watch"
    assert "超期" in result["reason"]


def test_exit_flag_on_price_up_but_fund_weakens():
    result = exit_flag({"sector": "证券", "pct_chg": 2.1, "main_net_inflow": -1e8})

    assert result["exit"] is False
    assert result["level"] == "watch"
    assert "量价背离" in result["reason"]


def test_turning_point_score_combines_multiple_warnings():
    result = turning_point_score(
        {
            "sector": "证券",
            "turning_point": True,
            "trend_days": 9,
            "pct_chg": 2.0,
            "main_net_inflow": -2e8,
            "inflow_5d": -5e8,
            "volume_amp": 2.0,
        },
        max_trend_days=7,
    )

    assert result["score"] >= 80
    assert result["level"] == "high"
    assert any("拐点" in reason for reason in result["reasons"])
    assert any("超期" in reason for reason in result["reasons"])
