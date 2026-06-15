"""Portfolio exposure helpers for sector offset risk."""

from __future__ import annotations

import pandas as pd


def build_portfolio_exposure(
    holdings: list[dict],
    stock_panel: pd.DataFrame,
    diagnostics: pd.DataFrame,
) -> pd.DataFrame:
    if not holdings:
        return pd.DataFrame(
            columns=[
                "sector",
                "market_value_wan",
                "weight",
                "fund_flow_yi",
                "money_direction",
                "trend_label",
                "split_label",
            ]
        )
    stock_lookup = _stock_lookup(stock_panel)
    rows = []
    for holding in holdings:
        code = str(holding.get("code", "")).zfill(6)
        stock = stock_lookup.get(code)
        if stock is None:
            continue
        shares = float(holding.get("shares") or 0.0)
        price = float(holding.get("price") or holding.get("cost") or 0.0)
        rows.append(
            {
                "sector": stock["sector"],
                "market_value_wan": shares * price,
            }
        )
    if not rows:
        return pd.DataFrame()
    exposure = pd.DataFrame(rows).groupby("sector", as_index=False).sum()
    total = exposure["market_value_wan"].sum()
    exposure["weight"] = exposure["market_value_wan"] / total if total else 0.0
    diag_cols = [
        "sector",
        "fund_flow_yi",
        "money_direction",
        "trend_label",
        "split_label",
    ]
    return exposure.merge(diagnostics[diag_cols], on="sector", how="left").fillna(
        {
            "fund_flow_yi": 0.0,
            "money_direction": "未知",
            "trend_label": "未知",
            "split_label": "未知",
        }
    )


def portfolio_offset_report(exposure: pd.DataFrame) -> dict:
    if exposure.empty:
        return {
            "offset_level": "none",
            "message": "暂无持仓，无法计算组合对冲。",
        }
    positive = exposure[exposure["fund_flow_yi"] > 0]
    negative = exposure[exposure["fund_flow_yi"] < 0]
    if positive.empty or negative.empty:
        return {
            "offset_level": "low",
            "message": "持仓板块资金方向相对一致，暂未看到明显对冲。",
        }
    positive_weight = float(positive["weight"].sum())
    negative_weight = float(negative["weight"].sum())
    offset_weight = min(positive_weight, negative_weight)
    level = "high" if offset_weight >= 0.35 else "medium"
    pos_names = "、".join(positive["sector"].astype(str).tolist())
    neg_names = "、".join(negative["sector"].astype(str).tolist())
    return {
        "offset_level": level,
        "offset_weight": offset_weight,
        "message": (
            f"{pos_names}资金净流入，但{neg_names}资金净流出；"
            f"组合约{offset_weight:.0%}权重暴露在相反资金方向，收益可能互相抵消。"
        ),
    }


def _stock_lookup(stock_panel: pd.DataFrame) -> dict[str, dict]:
    rows = {}
    for row in stock_panel.to_dict("records"):
        code = str(row.get("code") or row.get("symbol", "")[-6:]).zfill(6)
        rows[code] = row
    return rows
