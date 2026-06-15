"""Basic valuation summaries for sector-level context."""

from __future__ import annotations

import pandas as pd


def sector_valuation_snapshot(stocks: pd.DataFrame) -> pd.DataFrame:
    if stocks.empty or "sector" not in stocks.columns:
        return pd.DataFrame(
            columns=[
                "sector",
                "median_pe_ttm",
                "median_pb",
                "valuation_coverage",
                "valuation_label",
            ]
        )
    rows = []
    for sector, group in stocks.groupby("sector", sort=True):
        pe = pd.to_numeric(group.get("pe_ttm"), errors="coerce")
        pb = pd.to_numeric(group.get("pb"), errors="coerce")
        coverage = float(pe.notna().mean()) if len(group) else 0.0
        median_pe = float(pe.median()) if pe.notna().any() else None
        median_pb = float(pb.median()) if pb.notna().any() else None
        rows.append(
            {
                "sector": sector,
                "median_pe_ttm": median_pe,
                "median_pb": median_pb,
                "valuation_coverage": coverage,
                "valuation_label": _valuation_label(median_pe, coverage),
            }
        )
    return pd.DataFrame(rows)


def _valuation_label(median_pe: float | None, coverage: float) -> str:
    if coverage <= 0 or median_pe is None or pd.isna(median_pe):
        return "估值缺数据"
    if median_pe <= 12:
        return "低估值"
    if median_pe >= 35:
        return "高估值"
    return "中性估值"
