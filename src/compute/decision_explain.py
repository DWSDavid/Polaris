"""Decision explanation helpers for human-in-the-loop review."""

import pandas as pd


def explain_sector_state(
    state: str,
    diffusion: float,
    leader_contrib: float,
    fund_flow: float,
) -> dict:
    if state == "高位加速":
        return {
            "risk_level": "high",
            "action_hint": "避免追高，先用回撤情景检查仓位承受力。",
            "watch_points": "放量加速、回撤、龙头成交占比过高",
        }
    if state == "龙头孤立":
        return {
            "risk_level": "medium",
            "action_hint": "先看中军是否跟上，不把单一龙头脉冲当成板块共振。",
            "watch_points": "扩散不足、龙头独强、补涨缺席",
        }
    if state == "主升扩散":
        return {
            "risk_level": "medium" if leader_contrib > 0.7 else "low",
            "action_hint": "允许观察进攻机会，但仍需用担保比约束仓位。",
            "watch_points": "扩散延续、资金连续性、龙头分歧",
        }
    if state == "分歧退潮":
        return {
            "risk_level": "high",
            "action_hint": "降低进攻假设，优先保护担保比和流动性。",
            "watch_points": "资金流出、扩散收缩、弱修复失败",
        }
    if state == "低位修复":
        return {
            "risk_level": "medium",
            "action_hint": "观察修复质量，等待扩散和资金进一步确认。",
            "watch_points": "修复持续性、成交额回补、趋势反转失败",
        }
    risk = "medium" if diffusion < 0.4 or fund_flow < 0 else "low"
    return {
        "risk_level": risk,
        "action_hint": "信号未充分共振，先观察，不急于重仓。",
        "watch_points": "强度变化、扩散率、资金方向",
    }


def classify_stock_roles(stocks: pd.DataFrame) -> pd.DataFrame:
    out = stocks.copy()
    out["stock_role"] = out["rank"].apply(_role_for_rank)
    pct = out["pct_chg"] if "pct_chg" in out.columns else pd.Series(0, index=out.index)
    volume = (
        out["volume_ratio"]
        if "volume_ratio" in out.columns
        else pd.Series(0, index=out.index)
    )
    out["momentum_flag"] = ((pct.fillna(0) >= 3.0) & (volume.fillna(0) >= 1.5)).astype(
        object
    )
    return out


def _role_for_rank(rank) -> str:
    if rank <= 3:
        return "市值龙头"
    if rank <= 6:
        return "中军"
    return "跟随观察"


def enrich_decision_explanations(
    sector_panel: pd.DataFrame,
    stock_panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sectors = sector_panel.copy()
    explanations = [
        explain_sector_state(
            row.state,
            row.diffusion,
            row.leader_contrib,
            row.fund_flow,
        )
        for row in sectors.itertuples()
    ]
    for column in ["risk_level", "action_hint", "watch_points"]:
        sectors[column] = [item[column] for item in explanations]
    stocks = classify_stock_roles(stock_panel)
    return sectors, stocks
