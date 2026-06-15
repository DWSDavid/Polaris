from src.compute import config


def test_risk_lines_defaults():
    assert config.RISK_WARNING_LINE == 1.50
    assert config.RISK_LIQUIDATION_LINE == 1.30


def test_strength_weights_sum_to_one():
    assert abs(sum(config.STRENGTH_WEIGHTS.values()) - 1.0) < 1e-9
