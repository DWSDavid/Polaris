"""Style, theme, and macro regime research helpers."""

from __future__ import annotations

import akshare as ak
import pandas as pd


def style_spread(left: pd.Series, right: pd.Series) -> pd.Series:
    left_norm = _normalize_index(left)
    right_norm = _normalize_index(right)
    spread = left_norm.sub(right_norm, fill_value=0.0)
    return spread.dropna()


def detect_epochs(spread: pd.Series, min_abs: float = 0.0) -> list[dict]:
    series = pd.to_numeric(spread, errors="coerce").dropna()
    if series.empty:
        return []
    signs = series.map(lambda value: 1 if value >= min_abs else -1)
    epochs = []
    start_pos = 0
    current = int(signs.iloc[0])
    for pos, sign in enumerate(signs.iloc[1:], start=1):
        if int(sign) == current:
            continue
        epochs.append(_epoch(series, start_pos, pos - 1, current))
        start_pos = pos
        current = int(sign)
    epochs.append(_epoch(series, start_pos, len(series) - 1, current))
    return epochs


def dominant_theme(
    sector_timeline: pd.DataFrame,
    epoch: dict,
    top_n: int = 3,
) -> list[dict]:
    if sector_timeline.empty:
        return []
    frame = sector_timeline.copy()
    time_col = "week" if "week" in frame.columns else "date"
    start = str(epoch.get("start"))
    end = str(epoch.get("end"))
    frame[time_col] = frame[time_col].astype(str)
    frame = frame[(frame[time_col] >= start) & (frame[time_col] <= end)]
    if frame.empty:
        return []
    if "strength" not in frame.columns:
        frame["strength"] = pd.to_numeric(frame.get("pct_chg"), errors="coerce").fillna(0.0)
    if "main_net_inflow" not in frame.columns:
        frame["main_net_inflow"] = 0.0
    grouped = (
        frame.groupby("sector", as_index=False)
        .agg(
            avg_strength=("strength", "mean"),
            cum_inflow=("main_net_inflow", "sum"),
        )
        .sort_values(["avg_strength", "cum_inflow"], ascending=False)
        .head(int(top_n))
    )
    return grouped.to_dict("records")


def macro_context(start: str, end: str) -> pd.DataFrame:
    frames = [_fetch_cn_10y(), _fetch_northbound(), _fetch_margin()]
    merged = None
    for frame in frames:
        if frame.empty:
            continue
        frame = frame.copy()
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        merged = frame if merged is None else merged.merge(frame, on="date", how="outer")
    if merged is None:
        return pd.DataFrame(columns=["date", "cn_10y", "northbound_net", "margin_balance"])
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    merged = merged[(merged["date"] >= start_dt) & (merged["date"] <= end_dt)]
    return merged.sort_values("date").reset_index(drop=True)


def _epoch(series: pd.Series, start_pos: int, end_pos: int, sign: int) -> dict:
    return {
        "start": series.index[start_pos],
        "end": series.index[end_pos],
        "regime": "大盘占优" if sign >= 0 else "小盘占优",
        "start_value": float(series.iloc[start_pos]),
        "end_value": float(series.iloc[end_pos]),
    }


def _normalize_index(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return values
    first = float(values.iloc[0])
    if first == 0:
        return values * 0
    return values / first - 1


def _fetch_cn_10y() -> pd.DataFrame:
    raw = ak.bond_zh_us_rate()
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(raw["日期"], errors="coerce")
    out["cn_10y"] = pd.to_numeric(raw["中国国债收益率10年"], errors="coerce")
    return out.dropna(subset=["date"]).reset_index(drop=True)


def _fetch_northbound() -> pd.DataFrame:
    raw = ak.stock_hsgt_hist_em(symbol="北向资金")
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(raw["日期"], errors="coerce")
    out["northbound_net"] = pd.to_numeric(raw["当日成交净买额"], errors="coerce")
    out["northbound_inflow"] = pd.to_numeric(raw["当日资金流入"], errors="coerce")
    return out.dropna(subset=["date"]).reset_index(drop=True)


def _fetch_margin() -> pd.DataFrame:
    sh = _normalize_margin(ak.macro_china_market_margin_sh())
    sz = _normalize_margin(ak.macro_china_market_margin_sz())
    if sh.empty:
        return sz
    if sz.empty:
        return sh
    merged = sh.merge(sz, on="date", how="outer", suffixes=("_sh", "_sz"))
    merged["margin_balance"] = (
        pd.to_numeric(merged.get("margin_balance_sh"), errors="coerce").fillna(0)
        + pd.to_numeric(merged.get("margin_balance_sz"), errors="coerce").fillna(0)
    )
    return merged[["date", "margin_balance"]].sort_values("date").reset_index(drop=True)


def _normalize_margin(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["date", "margin_balance"])
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(raw["日期"], errors="coerce")
    out["margin_balance"] = pd.to_numeric(raw["融资融券余额"], errors="coerce")
    return out.dropna(subset=["date"]).reset_index(drop=True)
