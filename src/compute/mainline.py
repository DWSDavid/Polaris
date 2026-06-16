"""Medium-term mainline scoring for sector rotation."""

from __future__ import annotations

import pandas as pd

WEIGHTS = {
    "inflow_10d": 0.35,
    "trend_days": 0.25,
    "diffusion": 0.20,
    "pct_chg": 0.10,
    "amount": 0.10,
}


def mainline_score(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    amount = _num(out, "amount")
    amount_median = amount.median()
    out["mainline_liquidity_pass"] = amount.ge(amount_median) if pd.notna(amount_median) else True

    out["mainline_inflow_component"] = _zscore(_num(out, "inflow_10d")) * WEIGHTS["inflow_10d"]
    out["mainline_trend_component"] = _zscore(_num(out, "trend_days").clip(lower=0)) * WEIGHTS["trend_days"]
    out["mainline_diffusion_component"] = _zscore(_num(out, "diffusion")) * WEIGHTS["diffusion"]
    out["mainline_pct_component"] = _zscore(_num(out, "pct_chg")) * WEIGHTS["pct_chg"]
    out["mainline_amount_component"] = _zscore(amount) * WEIGHTS["amount"]
    out["mainline_raw_score"] = (
        out["mainline_inflow_component"]
        + out["mainline_trend_component"]
        + out["mainline_diffusion_component"]
        + out["mainline_pct_component"]
        + out["mainline_amount_component"]
    )
    out["mainline_score"] = out["mainline_raw_score"].where(
        out["mainline_liquidity_pass"], out["mainline_raw_score"] - 3.0
    )
    return out


def pick_mainline(scored: pd.DataFrame) -> str:
    if scored.empty:
        return ""
    candidates = scored[scored.get("mainline_liquidity_pass", True).astype(bool)]
    if candidates.empty:
        candidates = scored
    row = candidates.sort_values("mainline_score", ascending=False).iloc[0]
    return str(row.get("sector", ""))


def mainline_breakdown(row: pd.Series) -> str:
    liquidity = "成交通过" if bool(row.get("mainline_liquidity_pass", True)) else "成交低于中位数"
    return (
        f"10日资金 {_fmt(row.get('mainline_inflow_component'))} / "
        f"持续 {_fmt(row.get('mainline_trend_component'))} / "
        f"扩散 {_fmt(row.get('mainline_diffusion_component'))} / "
        f"今日 {_fmt(row.get('mainline_pct_component'))} / "
        f"成交 {_fmt(row.get('mainline_amount_component'))} ({liquidity})"
    )


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(0.0, index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def _zscore(values: pd.Series) -> pd.Series:
    series = pd.to_numeric(values, errors="coerce").fillna(0.0)
    std = series.std(ddof=0)
    if not std:
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std


def _fmt(value) -> str:
    if pd.isna(value):
        return "0.00"
    return f"{float(value):+.2f}"
