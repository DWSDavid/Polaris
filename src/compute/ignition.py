"""Early ignition detection for medium-term sector cycles."""

from __future__ import annotations


def ignition_score(feats: dict) -> float:
    position = _num(feats.get("position_in_box"))
    cum_inflow_20d = _num(feats.get("cum_inflow_20d"))
    volume_amp = _num(feats.get("volume_amp"), default=1.0)
    diffusion = _num(feats.get("diffusion"))
    midterm_trend = _num(feats.get("midterm_trend"))
    was_ranging = bool(feats.get("was_ranging"))

    score = 0.0
    if position >= 0.85 and was_ranging:
        score += 0.3
    elif position >= 0.75:
        score += 0.18
    if cum_inflow_20d > 0:
        score += 0.3
    if volume_amp >= 1.3:
        score += 0.2
    if diffusion >= 0.5:
        score += 0.15
    if midterm_trend > 0:
        score += 0.05
    return min(1.0, round(score, 4))


def ignition_flag(feats: dict, threshold: float = 0.6) -> bool:
    return _num(feats.get("cum_inflow_20d")) > 0 and ignition_score(feats) >= threshold


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
