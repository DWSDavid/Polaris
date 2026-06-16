"""Realtime snapshot orchestration for intraday Polaris views."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.data import cache
from src.data.universe import load_universe
from src.pipeline.refresh import SEED_UNIVERSE


def build_realtime_industry_panel(
    industry_spot: pd.DataFrame,
    industry_flow: pd.DataFrame | None = None,
) -> pd.DataFrame:
    out = industry_spot.copy()
    industry_flow = industry_flow if industry_flow is not None else pd.DataFrame()
    if not industry_flow.empty:
        out = out.merge(industry_flow, on="industry", how="left")
    else:
        out["today_main_net_inflow"] = pd.NA
        out["today_main_net_inflow_pct"] = pd.NA
    out["fund_flow_yi"] = (
        pd.to_numeric(out["today_main_net_inflow"], errors="coerce").fillna(0)
        / 100_000_000
    )
    out["money_direction"] = out["fund_flow_yi"].map(_money_direction)
    total_count = out["up_count"].fillna(0) + out["down_count"].fillna(0)
    out["diffusion"] = out["up_count"].fillna(0).where(
        total_count > 0, 0
    ) / total_count.where(total_count > 0, 1)
    out["data_quality"] = "realtime_snapshot"
    out["snapshot_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return out.sort_values(["pct_chg", "fund_flow_yi"], ascending=False).reset_index(
        drop=True
    )


def join_universe_realtime(
    universe: pd.DataFrame,
    stock_spot: pd.DataFrame,
) -> pd.DataFrame:
    out = universe.merge(stock_spot, on="code", how="left", suffixes=("", "_spot"))
    if "name_spot" in out.columns:
        out["name"] = out["name"].fillna(out["name_spot"])
    out["data_quality"] = (
        out["latest_price"]
        .notna()
        .map({True: "realtime_snapshot", False: "seed_static"})
    )
    return out.drop(columns=[col for col in ["name_spot", "symbol_spot"] if col in out])


def cached_realtime_industry_panel() -> pd.DataFrame:
    hit = cache.read("pipeline", "realtime_industry_panel", "latest")
    if hit is not None:
        return hit
    return pd.DataFrame()


def refresh_realtime_industry_panel() -> pd.DataFrame:
    from src.data import akshare_client

    industry = akshare_client.realtime_industry_spot()
    try:
        flows = akshare_client.realtime_industry_fund_flow()
    except Exception:
        flows = pd.DataFrame()
    panel = build_realtime_industry_panel(industry, flows)
    cache.write("pipeline", "realtime_industry_panel", "latest", panel)
    return panel


def safe_realtime_industry_panel() -> tuple[pd.DataFrame, str | None]:
    try:
        return refresh_realtime_industry_panel(), None
    except Exception as exc:
        cached = cached_realtime_industry_panel()
        if not cached.empty:
            return cached, str(exc)
        return cached, str(exc)


def realtime_industry_panel() -> pd.DataFrame:
    cached = cached_realtime_industry_panel()
    if not cached.empty:
        return cached
    return refresh_realtime_industry_panel()


def cached_realtime_stock_panel(limit: int | None = None) -> pd.DataFrame:
    hit = cache.read("pipeline", "realtime_stock_panel", "latest")
    if hit is not None:
        return hit.head(limit) if limit is not None else hit
    return pd.DataFrame()


def refresh_realtime_stock_panel(limit: int | None = None) -> pd.DataFrame:
    from src.data import akshare_client

    universe = load_universe(SEED_UNIVERSE)
    if limit is not None:
        universe = universe.head(limit).copy()
    spot = akshare_client.realtime_stock_spot()
    panel = join_universe_realtime(universe, spot)
    cache.write("pipeline", "realtime_stock_panel", "latest", panel)
    return panel


def realtime_stock_panel(limit: int | None = None) -> pd.DataFrame:
    cached = cached_realtime_stock_panel(limit)
    if not cached.empty:
        return cached
    return refresh_realtime_stock_panel(limit)


def _money_direction(value: float) -> str:
    if value > 0:
        return "净流入"
    if value < 0:
        return "净流出"
    return "持平"
