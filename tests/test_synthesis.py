from src.compute.synthesis import direction_score, rank_directions


def test_direction_score_rewards_aligned_signals():
    strong = {
        "sector": "电力设备",
        "midterm_trend": 1,
        "cum_inflow_20d": 40e8,
        "trend_days": 9,
        "ignition_flag": True,
        "northbound_pos": True,
        "lhb_active": True,
        "turning_point": False,
        "valuation_pct": 0.4,
        "hedge_penalty": 0.0,
    }
    weak = {
        "sector": "银行",
        "midterm_trend": 0,
        "cum_inflow_20d": -5e8,
        "trend_days": 1,
        "ignition_flag": False,
        "northbound_pos": False,
        "lhb_active": False,
        "turning_point": True,
        "valuation_pct": 0.9,
        "hedge_penalty": 0.3,
    }

    assert direction_score(strong) > direction_score(weak)
    ranked = rank_directions([strong, weak])

    assert ranked[0]["sector"] == "电力设备"
    assert "reasons" in ranked[0]


def test_rank_directions_uses_grounded_numeric_reasons():
    ranked = rank_directions(
        [
            {
                "sector": "电子",
                "midterm_trend": 1,
                "cum_inflow_20d": 2_400_000_000,
                "trend_days": 8,
                "ignition_flag": True,
                "northbound_pos": True,
                "lhb_active": False,
                "historical_win_rate": 0.62,
                "median_remaining_positive_days": 5,
                "valuation_pct": 0.45,
                "hedge_penalty": 0.1,
                "turning_point": False,
            }
        ]
    )

    top = ranked[0]
    joined = " ".join(top["reasons"])
    assert top["score"] > 0
    assert "20日资金+24.0亿" in joined
    assert "趋势持续8天" in joined
    assert "历史胜率62%" in joined
    assert "估值分位45%" in joined


def test_direction_score_penalizes_turning_point_high_valuation_and_hedge():
    base = {
        "sector": "证券",
        "midterm_trend": 1,
        "cum_inflow_20d": 1_000_000_000,
        "trend_days": 5,
        "ignition_flag": True,
        "northbound_pos": True,
        "lhb_active": True,
        "valuation_pct": 0.4,
        "hedge_penalty": 0.0,
        "turning_point": False,
    }
    risky = {
        **base,
        "turning_point": True,
        "valuation_pct": 0.95,
        "hedge_penalty": 0.5,
    }

    assert direction_score(base) > direction_score(risky)
    assert any("拐点" in item for item in rank_directions([risky])[0]["reasons"])
