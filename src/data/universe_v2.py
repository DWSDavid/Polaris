"""Dynamic Eastmoney industry universe for Polaris v2."""

from __future__ import annotations

import pandas as pd

from src.data import em_client

DEFAULT_MIN_MV = 2_000_000_000
DEFAULT_MIN_AMOUNT = 100_000_000
DEFAULT_MIN_LIST_DAYS = 365


def filter_noise(
    df: pd.DataFrame,
    min_mv: float = DEFAULT_MIN_MV,
    min_amount: float = DEFAULT_MIN_AMOUNT,
    min_list_days: int = DEFAULT_MIN_LIST_DAYS,
) -> pd.DataFrame:
    out = df.copy()
    names = out.get("name", pd.Series("", index=out.index)).fillna("").astype(str)
    is_st = out.get("is_st", pd.Series(False, index=out.index)).fillna(False).astype(bool)
    st_by_name = names.str.contains(r"^(?:ST|\*ST)|ST", regex=True, case=False)
    list_days = pd.to_numeric(
        out.get("list_days", pd.Series(min_list_days, index=out.index)),
        errors="coerce",
    ).fillna(0)
    total_mv = pd.to_numeric(out.get("total_mv"), errors="coerce")
    amount = pd.to_numeric(out.get("amount"), errors="coerce")

    keep = (
        ~is_st
        & ~st_by_name
        & list_days.ge(min_list_days)
        & total_mv.ge(min_mv)
        & amount.ge(min_amount)
    )
    return out.loc[keep].reset_index(drop=True)


def pick_leaders(df: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
    out = df.copy()
    out["leader_score"] = (
        _zscore(out.get("total_mv"))
        + _zscore(out.get("amount"))
        + _zscore(out.get("turnover"))
    )
    out = out.sort_values("leader_score", ascending=False).head(top_n).reset_index(
        drop=True
    )
    out["rank"] = range(1, len(out) + 1)
    out["leader_type"] = "market_cap"
    return out


def add_momentum_leaders(
    df: pd.DataFrame,
    manual_list: list[dict] | pd.DataFrame | None = None,
) -> pd.DataFrame:
    if manual_list is None:
        return df.copy().reset_index(drop=True)
    manual = pd.DataFrame(manual_list).copy()
    if manual.empty:
        return df.copy().reset_index(drop=True)

    base = df.copy()
    base["code"] = base["code"].astype(str).str.zfill(6)
    manual["code"] = manual["code"].astype(str).str.zfill(6)
    manual = manual[~manual["code"].isin(set(base["code"]))]
    if manual.empty:
        return base.reset_index(drop=True)

    for col in base.columns:
        if col not in manual.columns:
            manual[col] = pd.NA
    manual["leader_type"] = "momentum"
    return pd.concat([base, manual[base.columns]], ignore_index=True)


def build_universe(
    sectors: list[str] | None = None,
    top_n: int = 8,
    manual_list: list[dict] | pd.DataFrame | None = None,
    min_mv: float = DEFAULT_MIN_MV,
    min_amount: float = DEFAULT_MIN_AMOUNT,
    min_list_days: int = DEFAULT_MIN_LIST_DAYS,
) -> pd.DataFrame:
    sector_panel = em_client.industry_realtime()
    selected = sectors or sector_panel["sector"].dropna().tolist()
    market = em_client.market_spot()
    frames = []
    for sector in selected:
        candidates = _merge_market_metrics(em_client.industry_cons(sector), market)
        filtered = filter_noise(
            candidates,
            min_mv=min_mv,
            min_amount=min_amount,
            min_list_days=min_list_days,
        )
        if filtered.empty:
            continue
        frames.append(pick_leaders(filtered, top_n=top_n))
    if frames:
        universe = pd.concat(frames, ignore_index=True)
    else:
        universe = pd.DataFrame()
    return add_momentum_leaders(universe, manual_list)


def _merge_market_metrics(cons: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    market_cols = [
        "code",
        "latest_price",
        "pct_chg",
        "amount",
        "turnover",
        "volume_ratio",
        "pe_ttm",
        "pb",
        "total_mv",
        "circ_mv",
    ]
    available = [col for col in market_cols if col in market.columns]
    merged = cons.merge(market[available], on="code", how="left", suffixes=("", "_mkt"))
    for col in market_cols:
        mkt_col = f"{col}_mkt"
        if col in merged.columns and mkt_col in merged.columns:
            merged[col] = merged[col].combine_first(merged[mkt_col])
        elif mkt_col in merged.columns:
            merged[col] = merged[mkt_col]
    return merged.drop(columns=[col for col in merged.columns if col.endswith("_mkt")])


def _zscore(values) -> pd.Series:
    series = pd.to_numeric(values, errors="coerce").fillna(0.0)
    std = series.std(ddof=0)
    if not std:
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std
