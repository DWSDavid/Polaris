import pandas as pd

from src.compute import indicators as ind


def test_diffusion_rate():
    changes = pd.Series([0.02, -0.01, 0.03, 0.00, 0.01])
    assert abs(ind.diffusion_rate(changes) - 0.6) < 1e-9


def test_leader_contribution():
    turnover = pd.Series([100, 80, 60, 40, 20])
    assert abs(ind.leader_contribution(turnover, top_n=3) - 0.8) < 1e-9


def test_volume_amplification():
    hist = pd.Series([10, 10, 10, 10, 20])
    assert ind.volume_amplification(hist, window=5) > 1.0
