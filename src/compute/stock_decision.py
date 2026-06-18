"""Single-stock decision facts and setup scoring."""

from __future__ import annotations

import pandas as pd

from src.compute.cycle import box_range, cum_inflow, midterm_trend, position_in_box
from src.compute.pattern_risk import detect_bull_trap_risk, historical_trap_report


POSITIVE_SECTOR_STATES = {"主升扩散", "冷启动", "低位修复"}
WEAK_SECTOR_STATES = {"分歧退潮", "主力分化"}


def build_stock_facts(
    stock: dict | pd.Series,
    daily: pd.DataFrame,
    flow: pd.DataFrame | None = None,
    sector: dict | pd.Series | None = None,
    holding: dict | None = None,
) -> dict:
    stock_data = _as_dict(stock)
    sector_data = _as_dict(sector or {})
    holding = holding or {}
    closes = _series(daily, "close")
    price = _num(stock_data.get("latest_price"), _last(closes))
    high, low = box_range(closes, window=60)
    ma20 = _ma(closes, 20)
    ma60 = _ma(closes, 60)
    has_ma20 = len(closes) >= 20 and ma20 > 0
    has_ma60 = len(closes) >= 60 and ma60 > 0
    pct_chg = _num(stock_data.get("pct_chg"), _last(_pct_series(daily)))
    flow_values = _flow_values(flow)
    stock_inflow_5d = cum_inflow(flow_values, window=5)
    stock_inflow_10d = cum_inflow(flow_values, window=10)
    holding_cost = _num(holding.get("cost"), 0.0)

    facts = {
        "code": str(stock_data.get("code", "")).zfill(6) if stock_data.get("code") else "",
        "symbol": str(stock_data.get("symbol", "")),
        "name": str(stock_data.get("name", "")),
        "sector": str(sector_data.get("sector") or stock_data.get("sector") or ""),
        "group": str(sector_data.get("group") or stock_data.get("group") or ""),
        "latest_price": round(price, 3),
        "pct_chg": round(pct_chg, 3),
        "amount": _num(stock_data.get("amount")),
        "volume_ratio": _num(stock_data.get("volume_ratio"), 1.0),
        "turnover_rate": _num(stock_data.get("turnover_rate"), _num(stock_data.get("turnover"))),
        "pe_ttm": _none_if_zero(stock_data.get("pe_ttm")),
        "pb": _none_if_zero(stock_data.get("pb")),
        "total_mv": _num(stock_data.get("total_mv")),
        "ma20": round(ma20, 3),
        "ma60": round(ma60, 3),
        "above_ma20": bool(price >= ma20) if has_ma20 else None,
        "above_ma60": bool(price >= ma60) if has_ma60 else None,
        "midterm_trend": midterm_trend(closes, short=20, long=60),
        "return_20d": round(_return_pct(closes, 20), 3),
        "return_60d": round(_return_pct(closes, 60), 3),
        "drawdown_60d": round(_drawdown(closes), 4),
        "position_in_box": round(position_in_box(price, high, low), 3),
        "stock_inflow_latest": _last(flow_values),
        "stock_inflow_5d": stock_inflow_5d,
        "stock_inflow_10d": stock_inflow_10d,
        "sector_state": str(sector_data.get("state", "未知")),
        "sector_trend_days": int(round(_num(sector_data.get("trend_days")))),
        "sector_inflow_10d": _num(sector_data.get("inflow_10d")),
        "sector_main_net_inflow": _num(sector_data.get("main_net_inflow")),
        "sector_pct_chg": _num(sector_data.get("pct_chg")),
        "sector_turning_point": bool(sector_data.get("turning_point", False)),
        "sector_top_leaders": str(sector_data.get("top_leaders", "")),
    }
    history_for_pattern = _history_with_flow(daily, flow)
    if not history_for_pattern.empty:
        facts["pattern_risk"] = detect_bull_trap_risk(history_for_pattern)
        facts["historical_trap"] = historical_trap_report(history_for_pattern)
    facts["relative_to_sector_today"] = round(facts["pct_chg"] - facts["sector_pct_chg"], 3)
    if holding_cost > 0 and price > 0:
        facts["holding_cost"] = holding_cost
        facts["holding_return"] = round((price - holding_cost) / holding_cost, 4)
        facts["holding_shares"] = _num(holding.get("shares"))
    return facts


def evaluate_stock_setup(facts: dict) -> dict:
    score = 0.0
    reasons: list[str] = []
    risk_flags = _risk_flags(facts)

    sector_state = str(facts.get("sector_state", ""))
    if sector_state in POSITIVE_SECTOR_STATES:
        score += 2.0 if sector_state == "主升扩散" else 1.0
        reasons.append("行业主线支持")
    elif sector_state in WEAK_SECTOR_STATES:
        score -= 2.0

    if _num(facts.get("sector_inflow_10d")) > 0:
        score += 1.0
    elif _num(facts.get("sector_inflow_10d")) < 0:
        score -= 1.0

    if facts.get("above_ma20") is True:
        score += 1.0
    elif facts.get("above_ma20") is False:
        score -= 0.8
    if facts.get("above_ma60") is True:
        score += 1.2
    elif facts.get("above_ma60") is False:
        score -= 1.5
    if _num(facts.get("midterm_trend")) > 0:
        score += 1.0
        reasons.append("个股中期结构向上")
    elif _num(facts.get("midterm_trend")) < 0:
        score -= 1.0

    if _num(facts.get("stock_inflow_5d")) > 0:
        score += 0.8
        reasons.append("个股资金转正")
    else:
        score -= 0.6
    if _num(facts.get("stock_inflow_10d")) > 0:
        score += 0.8
    elif _num(facts.get("stock_inflow_10d")) < 0:
        score -= 0.8

    position = _num(facts.get("position_in_box"), 0.5)
    if 0.35 <= position <= 0.85:
        score += 0.7
    elif position > 0.9:
        score -= 1.2

    if _num(facts.get("relative_to_sector_today")) > 0:
        score += 0.4
        reasons.append("相对行业更强")
    if bool(facts.get("sector_turning_point")):
        score -= 1.5
    if _num(facts.get("holding_return")) <= -0.10:
        score -= 1.5
    pattern_score = _num((facts.get("pattern_risk") or {}).get("risk_score"))
    if pattern_score >= 0.7:
        score -= 1.5
    elif pattern_score >= 0.45:
        score -= 0.7

    volume_ratio = _num(facts.get("volume_ratio"), 1.0)
    if 1.1 <= volume_ratio <= 2.5:
        score += 0.3
    elif volume_ratio >= 3.0:
        score -= 0.5

    stance = _stance(facts, score, risk_flags)
    return {
        "stance": stance,
        "score": round(score, 2),
        "reasons": reasons or ["缺少足够共振，先观察"],
        "risk_flags": risk_flags,
        "watch_points": _watch_points(facts, stance),
    }


def _stance(facts: dict, score: float, risk_flags: list[str]) -> str:
    has_holding = "holding_return" in facts
    broken = "跌破60日均线" in risk_flags
    severe_drawdown = "持仓回撤超过10%" in risk_flags
    high_position = "箱体位置过高" in risk_flags
    flow_out = "个股资金连续流出" in risk_flags
    sector_bad = str(facts.get("sector_state")) in WEAK_SECTOR_STATES or bool(
        facts.get("sector_turning_point")
    )

    if has_holding and ((broken and sector_bad) or (severe_drawdown and broken) or (flow_out and broken)):
        return "减仓/退出观察"
    if high_position:
        return "不追高，等回踩确认"
    if has_holding:
        return "继续持有观察" if score >= 3.0 else "降低仓位假设"
    if score >= 5.0 and not risk_flags:
        return "适合观察入场"
    if score >= 3.0:
        return "观察等待确认"
    return "暂不入场"


def _risk_flags(facts: dict) -> list[str]:
    flags: list[str] = []
    if facts.get("above_ma60") is False:
        flags.append("跌破60日均线")
    if _num(facts.get("holding_return")) <= -0.10:
        flags.append("持仓回撤超过10%")
    if _num(facts.get("position_in_box"), 0.5) >= 0.9 and (
        _num(facts.get("volume_ratio"), 1.0) >= 3.0
        or str(facts.get("sector_state")) == "高位加速"
    ):
        flags.append("箱体位置过高")
    if bool(facts.get("sector_turning_point")):
        flags.append("行业拐点预警")
    if _num(facts.get("stock_inflow_5d")) < 0 and _num(facts.get("stock_inflow_10d")) < 0:
        flags.append("个股资金连续流出")
    if _num(facts.get("volume_ratio"), 1.0) >= 3.0:
        flags.append("放量过猛")
    if (facts.get("pattern_risk") or {}).get("label") == "疑似诱多风险":
        flags.append("疑似诱多风险")
    return flags


def _watch_points(facts: dict, stance: str) -> list[str]:
    name = facts.get("name") or facts.get("code") or "该股"
    points = [
        f"{name}能否继续站上20日和60日均线",
        "5日与10日主力资金是否继续为正",
        f"{facts.get('sector', '所属行业')}是否保持资金和阶段共振",
    ]
    if stance == "不追高，等回踩确认":
        points.insert(0, "箱体高位不追，等回踩或放量换手后的二次确认")
    if (facts.get("pattern_risk") or {}).get("label") == "疑似诱多风险":
        points.insert(0, "先看反弹能否站回60日线且资金转正，避免只接最后一段反抽")
    return points


def _history_with_flow(daily: pd.DataFrame, flow: pd.DataFrame | None) -> pd.DataFrame:
    if daily is None or daily.empty or "close" not in daily.columns:
        return pd.DataFrame()
    history = daily.copy()
    if "main_net_inflow" in history.columns:
        return history
    flow_values = _flow_values(flow)
    if flow_values.empty:
        return history
    history = history.reset_index(drop=True)
    flow_tail = flow_values.reset_index(drop=True).tail(len(history)).reset_index(drop=True)
    if len(flow_tail) < len(history):
        pad = pd.Series([0.0] * (len(history) - len(flow_tail)))
        flow_tail = pd.concat([pad, flow_tail], ignore_index=True)
    history["main_net_inflow"] = flow_tail.tail(len(history)).to_numpy()
    return history


def _as_dict(value) -> dict:
    if value is None:
        return {}
    if isinstance(value, pd.Series):
        return value.to_dict()
    return dict(value)


def _series(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").dropna()


def _pct_series(frame: pd.DataFrame) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=float)
    for column in ("pct_chg", "pct", "涨跌幅"):
        if column in frame.columns:
            return pd.to_numeric(frame[column], errors="coerce").dropna()
    return pd.Series(dtype=float)


def _flow_values(flow: pd.DataFrame | None) -> pd.Series:
    if flow is None or flow.empty:
        return pd.Series(dtype=float)
    for column in ("main_net_inflow", "主力净流入-净额", "主力净流入净额"):
        if column in flow.columns:
            return pd.to_numeric(flow[column], errors="coerce").fillna(0)
    return pd.Series(dtype=float)


def _ma(series: pd.Series, window: int) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return 0.0
    return float(values.tail(min(window, len(values))).mean())


def _return_pct(series: pd.Series, window: int) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if len(values) < 2:
        return 0.0
    tail = values.tail(min(window + 1, len(values)))
    start = float(tail.iloc[0])
    end = float(tail.iloc[-1])
    if start == 0:
        return 0.0
    return (end / start - 1) * 100


def _drawdown(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna().tail(60)
    if values.empty:
        return 0.0
    high = float(values.max())
    latest = float(values.iloc[-1])
    if high == 0:
        return 0.0
    return latest / high - 1


def _last(series: pd.Series, default: float = 0.0) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return default
    return float(values.iloc[-1])


def _num(value, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _none_if_zero(value):
    number = _num(value)
    return None if number == 0 else number
