"""Centralized tunable parameters for Polaris."""

RISK_WARNING_LINE = 1.50
RISK_LIQUIDATION_LINE = 1.30

STRENGTH_WEIGHTS = {
    "relative_return": 0.20,
    "volume_amp": 0.20,
    "fund_flow": 0.20,
    "breadth": 0.20,
    "leader_contrib": 0.20,
}

DIFFUSION_HIGH = 0.60
DIFFUSION_LOW = 0.40
VOLUME_BLOWOFF = 2.0

WINDOW_SHORT = 5
WINDOW_LONG = 20
