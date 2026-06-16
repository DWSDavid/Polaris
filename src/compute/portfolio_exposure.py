"""Portfolio exposure helpers for sector offset risk."""

from __future__ import annotations

import pandas as pd

from src.compute.divergence import hedge_pairs, hedge_score

STOCK_SECTOR_OVERRIDES = {
    "601688": "证券",
}


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
        sector = resolve_holding_sector(holding)
        if not sector and stock is not None:
            sector = stock.get("sector")
        available_sectors = diagnostics["sector"] if "sector" in diagnostics.columns else []
        sector = match_sector_name(sector, available_sectors) if sector else sector
        if not sector:
            continue
        shares = float(holding.get("shares") or 0.0)
        price = float(holding.get("price") or holding.get("cost") or 0.0)
        rows.append(
            {
                "sector": sector,
                "market_value_wan": shares * price,
            }
        )
    if not rows:
        return pd.DataFrame()
    exposure = pd.DataFrame(rows).groupby("sector", as_index=False).sum()
    total = exposure["market_value_wan"].sum()
    exposure["weight"] = exposure["market_value_wan"] / total if total else 0.0
    diag_cols = ["sector"]
    desired_cols = [
        "fund_flow_yi",
        "money_direction",
        "trend_label",
        "split_label",
        "state",
        "trend_days",
        "turning_point",
    ]
    diag_cols.extend([col for col in desired_cols if col in diagnostics.columns])
    merged = exposure.merge(diagnostics[diag_cols], on="sector", how="left")
    fill_values = {
        "fund_flow_yi": 0.0,
        "money_direction": "未知",
        "trend_label": "未知",
        "split_label": "未知",
        "state": "未知",
        "trend_days": 0,
        "turning_point": False,
    }
    for col, fallback in fill_values.items():
        if col not in merged.columns:
            merged[col] = fallback
    return merged.fillna(fill_values)


def portfolio_offset_report(exposure: pd.DataFrame, corr: pd.DataFrame | None = None) -> dict:
    if exposure.empty:
        return {
            "offset_level": "none",
            "message": "暂无持仓，无法计算组合对冲。",
        }
    if exposure["sector"].dropna().astype(str).nunique() <= 1:
        sector = str(exposure["sector"].dropna().iloc[0]) if "sector" in exposure and not exposure["sector"].dropna().empty else "当前行业"
        return {
            "offset_level": "none",
            "message": f"单一持仓集中在{sector}，当前无行业对冲；加入候选篮子后再计算对冲度。",
        }
    sectors = exposure["sector"].dropna().astype(str).tolist()
    pairs = hedge_pairs(sectors, corr, threshold=-0.3) if corr is not None else []
    if pairs:
        score = hedge_score(sectors, corr)
        names = "、".join(f"{left}↔{right}" for left, right in pairs)
        return {
            "offset_level": "high" if score >= 0.5 else "medium",
            "hedge_score": score,
            "hedge_pairs": pairs,
            "message": f"组合存在历史负相关对冲：{names}，对冲度约 {score:.0%}，收益可能互相抵消。",
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


def resolve_holding_sector(holding: dict, fallback: str | None = None) -> str | None:
    code = str(holding.get("code", "")).zfill(6)
    if code in STOCK_SECTOR_OVERRIDES:
        return STOCK_SECTOR_OVERRIDES[code]
    return str(holding.get("sector") or fallback or "") or None


def match_sector_name(sector: str | None, available) -> str | None:
    if not sector:
        return None
    target = str(sector)
    values = [str(item) for item in available if str(item)]
    if target in values:
        return target
    if target == "证券":
        for preferred in ("证券Ⅱ", "证券II", "证券Ⅲ", "证券III"):
            if preferred in values:
                return preferred
        for value in values:
            if value.startswith("证券"):
                return value
    return target
