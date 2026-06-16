"""Direction-level signal synthesis for medium-term sector decisions."""

from __future__ import annotations

from typing import Iterable


def direction_score(facts: dict) -> float:
    """Score one sector/direction from already-computed, grounded signals."""
    midterm = _num(facts.get("midterm_trend"))
    inflow_yi = _num(facts.get("cum_inflow_20d")) / 100_000_000
    trend_days = max(0.0, _num(facts.get("trend_days")))
    valuation_pct = facts.get("valuation_pct")
    hedge_penalty = max(0.0, _num(facts.get("hedge_penalty")))

    score = 0.0
    if midterm > 0:
        score += 1.6
    elif midterm < 0:
        score -= 1.2

    score += _clip(inflow_yi, -60, 60) * 0.04
    score += min(trend_days, 15) * 0.12

    if bool(facts.get("ignition_flag")):
        score += 1.0
    if bool(facts.get("northbound_pos")):
        score += 0.5
    if bool(facts.get("lhb_active")):
        score += 0.45

    win_rate = facts.get("historical_win_rate")
    if win_rate is not None:
        score += (_num(win_rate) - 0.5) * 2.0
    remaining = facts.get("median_remaining_positive_days")
    if remaining is not None:
        score += min(max(_num(remaining), 0.0), 10.0) * 0.08

    if bool(facts.get("turning_point")):
        score -= 1.2
    if valuation_pct is not None:
        pct = _num(valuation_pct)
        if pct >= 0.85:
            score -= 1.0
        elif pct >= 0.7:
            score -= 0.5
        elif pct <= 0.5:
            score += 0.2
    score -= hedge_penalty * 2.0

    return round(float(score), 4)


def rank_directions(candidates: Iterable[dict]) -> list[dict]:
    ranked = []
    for facts in candidates:
        item = dict(facts)
        item["score"] = direction_score(facts)
        item["reasons"] = _reasons(facts)
        ranked.append(item)
    return sorted(ranked, key=lambda item: item["score"], reverse=True)


def _reasons(facts: dict) -> list[str]:
    reasons: list[str] = []
    midterm = _num(facts.get("midterm_trend"))
    inflow = facts.get("cum_inflow_20d")
    trend_days = facts.get("trend_days")
    valuation_pct = facts.get("valuation_pct")
    hedge_penalty = _num(facts.get("hedge_penalty"))

    if midterm > 0:
        reasons.append("中期趋势向上")
    elif midterm < 0:
        reasons.append("中期趋势向下")
    if inflow is not None:
        reasons.append(f"20日资金{_num(inflow) / 100_000_000:+.1f}亿")
    if trend_days is not None:
        reasons.append(f"趋势持续{int(_num(trend_days))}天")
    if bool(facts.get("ignition_flag")):
        reasons.append("启动迹象已满足")
    if bool(facts.get("northbound_pos")):
        reasons.append("北向资金同向")
    if bool(facts.get("lhb_active")):
        reasons.append("龙虎榜活跃")
    if facts.get("historical_win_rate") is not None:
        reasons.append(f"历史胜率{_num(facts.get('historical_win_rate')):.0%}")
    if facts.get("median_remaining_positive_days") is not None:
        reasons.append(
            f"历史中位还能走{_num(facts.get('median_remaining_positive_days')):.0f}天"
        )
    if valuation_pct is not None:
        pct = _num(valuation_pct)
        label = "，偏拥挤" if pct >= 0.85 else ""
        reasons.append(f"估值分位{pct:.0%}{label}")
    if hedge_penalty > 0:
        reasons.append(f"对冲惩罚{hedge_penalty:.0%}")
    if bool(facts.get("turning_point")):
        reasons.append("拐点预警")
    return reasons or ["缺少可验证信号，先观察"]


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clip(value: float, lower: float, upper: float) -> float:
    return min(max(float(value), lower), upper)
