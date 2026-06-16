"""Exit discipline signals for medium-term swing positions."""

from __future__ import annotations

import pandas as pd


def exit_flag(row: dict | pd.Series, max_trend_days: int | None = None) -> dict:
    data = dict(row)
    sector = str(data.get("sector", ""))
    if bool(data.get("turning_point", False)):
        return {"exit": True, "reason": f"{sector} 出现拐点，考虑减仓。"}

    trend_days = int(data.get("trend_days", 0) or 0)
    if max_trend_days is not None and trend_days >= max_trend_days:
        return {
            "exit": True,
            "reason": f"{sector} 趋势已持续 {trend_days} 天，超过纪律阈值，属于超期提醒。",
        }

    pct_chg = float(data.get("pct_chg", 0) or 0)
    main_net_inflow = float(data.get("main_net_inflow", 0) or 0)
    if pct_chg > 0 and main_net_inflow < 0:
        return {
            "exit": True,
            "reason": f"{sector} 价格仍涨但主力资金转弱，出现量价背离。",
        }

    return {"exit": False, "reason": ""}


def turning_point_score(
    row: dict | pd.Series,
    max_trend_days: int | None = None,
) -> dict:
    data = dict(row)
    sector = str(data.get("sector", "当前行业"))
    score = 0
    reasons = []

    if bool(data.get("turning_point", False)):
        score += 35
        reasons.append(f"{sector} 出现拐点信号")

    trend_days = int(data.get("trend_days", 0) or 0)
    if max_trend_days is not None and trend_days >= max_trend_days:
        score += 25
        reasons.append(f"{sector} 趋势已持续 {trend_days} 天，属于超期提醒")

    pct_chg = float(data.get("pct_chg", 0) or 0)
    main_net_inflow = float(data.get("main_net_inflow", 0) or 0)
    if pct_chg > 0 and main_net_inflow < 0:
        score += 25
        reasons.append(f"{sector} 价格仍涨但主力流出，量价背离")

    inflow_5d = float(data.get("inflow_5d", 0) or 0)
    if inflow_5d < 0:
        score += 10
        reasons.append(f"{sector} 5日资金转弱")

    volume_amp = float(data.get("volume_amp", 1) or 1)
    if volume_amp >= 1.8 and pct_chg <= 0:
        score += 10
        reasons.append(f"{sector} 放量但价格不跟，承接变弱")

    score = min(100, score)
    return {
        "score": score,
        "level": _score_level(score),
        "reasons": reasons,
        "message": "；".join(reasons) if reasons else f"{sector} 暂无明显拐点组合信号",
    }


def _score_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 35:
        return "medium"
    return "low"
