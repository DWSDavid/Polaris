from src.compute.ignition import ignition_flag, ignition_score


def test_ignition_when_breakout_with_money():
    feats = {
        "position_in_box": 0.92,
        "cum_inflow_20d": 8e8,
        "volume_amp": 1.6,
        "diffusion": 0.62,
        "midterm_trend": 1,
        "was_ranging": True,
    }

    assert ignition_score(feats) > 0.6
    assert ignition_flag(feats) is True


def test_no_ignition_when_no_money():
    feats = {
        "position_in_box": 0.92,
        "cum_inflow_20d": -3e8,
        "volume_amp": 0.9,
        "diffusion": 0.35,
        "midterm_trend": 0,
        "was_ranging": True,
    }

    assert ignition_flag(feats) is False
