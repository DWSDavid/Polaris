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
