"""Historical trap and bull-trap style pattern detection."""

from __future__ import annotations

import pandas as pd


def detect_bull_trap_risk(
    history: pd.DataFrame,
    bounce_days: int = 3,
    down_window: int = 20,
    ma_window: int = 60,
) -> dict:
    frame = _prepare(history)
    if len(frame) < max(bounce_days + down_window, ma_window):
        return _report("样本不足", 0.0, [], frame)

    closes = frame["close"]
    latest = float(closes.iloc[-1])
    ma60 = float(closes.tail(ma_window).mean())
    prev = closes.iloc[-bounce_days - down_window : -bounce_days]
    recent = closes.tail(bounce_days)
    down_return = _return(prev)
    bounce_return = _return(recent)
    recent_flow = _recent_flow(frame, bounce_days)
    volume_spike = _volume_spike(frame, bounce_days)
    drawdown = _drawdown(closes.tail(ma_window))

    score = 0.0
    reasons: list[str] = []
    if down_return <= -0.08 or drawdown <= -0.12:
        score += 0.28
        reasons.append("前序中期下行")
    if bounce_return >= 0.035:
        score += 0.24
        reasons.append("短线快速反弹")
    if latest < ma60:
        score += 0.22
        reasons.append("中期仍在60日线下")
    if recent_flow < 0:
        score += 0.22
        reasons.append("反弹资金背离")
    if volume_spike and recent_flow <= 0:
        score += 0.12
        reasons.append("放量但资金不跟")

    score = min(1.0, round(score, 3))
    if score >= 0.7:
        label = "疑似诱多风险"
    elif score >= 0.45:
        label = "反弹需验证"
    else:
        label = "结构未显示诱多"
    return _report(
        label,
        score,
        reasons,
        frame,
        down_return=down_return,
        bounce_return=bounce_return,
        recent_flow=recent_flow,
        drawdown=drawdown,
    )


def historical_trap_report(
    history: pd.DataFrame,
    horizons: tuple[int, ...] = (3, 5, 10),
    min_score: float = 0.65,
) -> dict:
    frame = _prepare(history)
    if frame.empty:
        return _empty_history_report()
    rows = []
    max_horizon = max(horizons)
    for end in range(60, len(frame) - max_horizon):
        window = frame.iloc[: end + 1].copy()
        risk = detect_bull_trap_risk(window)
        if risk["risk_score"] < min_score:
            continue
        close = float(frame.iloc[end]["close"])
        sample = {
            "trade_date": str(frame.iloc[end].get("trade_date", frame.iloc[end].get("date", ""))),
            "risk_score": risk["risk_score"],
        }
        for horizon in horizons:
            future = frame.iloc[end + 1 : end + horizon + 1]["close"]
            sample[f"forward_return_{horizon}d"] = (
                float(future.iloc[-1] / close - 1) if len(future) >= horizon and close else pd.NA
            )
        rows.append(sample)
    samples = pd.DataFrame(rows)
    if samples.empty:
        return _empty_history_report()

    report = {"sample_count": int(len(samples))}
    for horizon in horizons:
        values = pd.to_numeric(samples[f"forward_return_{horizon}d"], errors="coerce").dropna()
        report[f"median_forward_return_{horizon}d"] = float(values.median()) if len(values) else 0.0
        report[f"win_rate_{horizon}d"] = float((values > 0).mean()) if len(values) else 0.0
    report["summary"] = _history_summary(report)
    return report


def _prepare(history: pd.DataFrame) -> pd.DataFrame:
    if history is None or history.empty or "close" not in history.columns:
        return pd.DataFrame(columns=["close"])
    frame = history.copy()
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    if "pct_chg" in frame.columns:
        frame["pct_chg"] = pd.to_numeric(frame["pct_chg"], errors="coerce").fillna(0)
    elif "pct" in frame.columns:
        frame["pct_chg"] = pd.to_numeric(frame["pct"], errors="coerce").fillna(0)
    else:
        frame["pct_chg"] = frame["close"].pct_change().fillna(0) * 100
    if "amount" in frame.columns:
        frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce").fillna(0)
    else:
        frame["amount"] = 0.0
    frame["main_net_inflow"] = _flow_series(frame)
    return frame.dropna(subset=["close"]).reset_index(drop=True)


def _flow_series(frame: pd.DataFrame) -> pd.Series:
    for column in ("main_net_inflow", "主力净流入-净额", "主力净流入净额"):
        if column in frame.columns:
            return pd.to_numeric(frame[column], errors="coerce").fillna(0)
    return pd.Series(0.0, index=frame.index)


def _return(values: pd.Series) -> float:
    nums = pd.to_numeric(values, errors="coerce").dropna()
    if len(nums) < 2 or float(nums.iloc[0]) == 0:
        return 0.0
    return float(nums.iloc[-1] / nums.iloc[0] - 1)


def _recent_flow(frame: pd.DataFrame, days: int) -> float:
    return float(pd.to_numeric(frame["main_net_inflow"], errors="coerce").fillna(0).tail(days).sum())


def _volume_spike(frame: pd.DataFrame, days: int) -> bool:
    amount = pd.to_numeric(frame["amount"], errors="coerce").fillna(0)
    if amount.tail(days).mean() <= 0:
        return False
    base = amount.iloc[:-days].tail(20).mean()
    if base <= 0:
        return False
    return float(amount.tail(days).mean() / base) >= 1.35


def _drawdown(values: pd.Series) -> float:
    nums = pd.to_numeric(values, errors="coerce").dropna()
    if nums.empty:
        return 0.0
    high = float(nums.max())
    if high == 0:
        return 0.0
    return float(nums.iloc[-1] / high - 1)


def _report(
    label: str,
    score: float,
    reasons: list[str],
    frame: pd.DataFrame,
    **extra,
) -> dict:
    return {
        "label": label,
        "risk_score": float(score),
        "reasons": reasons,
        "sample_days": int(len(frame)),
        **extra,
    }


def _history_summary(report: dict) -> str:
    sample_count = int(report.get("sample_count", 0))
    median = float(report.get("median_forward_return_5d", report.get("median_forward_return_3d", 0)))
    win_rate = float(report.get("win_rate_5d", report.get("win_rate_3d", 0)))
    return (
        f"历史疑似诱多样本 {sample_count} 个：后续中位收益 {median:+.1%}，"
        f"胜率 {win_rate:.0%}。这是历史分布，不是买卖指令。"
    )


def _empty_history_report() -> dict:
    return {
        "sample_count": 0,
        "summary": "历史疑似诱多样本不足，暂时不能下结论。",
    }
