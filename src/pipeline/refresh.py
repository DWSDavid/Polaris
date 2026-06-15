"""End-of-day orchestration helpers."""

from pathlib import Path

import pandas as pd

from src.compute import config, indicators
from src.compute.state_machine import classify_state
from src.data import cache
from src.data.universe import load_universe

SEED_UNIVERSE = Path("data/universe/sector_leaders_seed.xlsx")


def build_sector_panel(features: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    out["strength"] = indicators.sector_strength(features, config.STRENGTH_WEIGHTS)
    out["strength_rank"] = out["strength"].rank(pct=True)
    out["state"] = [
        classify_state(
            row.strength_rank,
            row.diffusion,
            row.fund_inflow,
            row.volume_amp,
            row.trend20,
            row.consecutive_up,
        )
        for row in out.itertuples()
    ]
    out["state_note"] = out.apply(_state_note, axis=1)
    return out


def _state_note(row) -> str:
    if row.state == "主升扩散":
        return "强度靠前，扩散率高，资金条件为正。"
    if row.state == "龙头孤立":
        return "强度靠前但扩散率偏低，先看龙头能否带动中军。"
    if row.state == "高位加速":
        return "强度极高且放量加速，重点检查追高和回撤风险。"
    if row.state == "分歧退潮":
        return "强度和资金条件偏弱，先降低进攻假设。"
    if row.state == "低位修复":
        return "趋势仍弱但有修复迹象，适合观察不适合重仓确认。"
    return "信号未充分共振，先观察资金和扩散能否继续改善。"


def build_universe_panels(path: Path = SEED_UNIVERSE) -> tuple[pd.DataFrame, pd.DataFrame]:
    universe = load_universe(path)
    grouped = universe.groupby("sector", sort=True)
    sector_base = grouped.agg(
        stock_count=("code", "count"),
        total_market_cap=("market_cap", "sum"),
        coverage=("sector_share", "sum"),
        index_weight=("index_weight", "sum"),
        leader_contrib=("sector_share", lambda s: float(s.nlargest(3).sum())),
    )
    sector_base["top_leaders"] = grouped.apply(
        lambda g: "、".join(g.sort_values("rank").head(3)["name"].tolist()),
        include_groups=False,
    )

    features = pd.DataFrame(index=sector_base.index)
    features["relative_return"] = sector_base["total_market_cap"].rank(pct=True)
    features["volume_amp"] = 1.0 + sector_base["coverage"].fillna(0)
    features["fund_flow"] = sector_base["index_weight"].fillna(0)
    features["breadth"] = (sector_base["coverage"] / sector_base["coverage"].max()).fillna(0)
    features["leader_contrib"] = sector_base["leader_contrib"].fillna(0)
    features["diffusion"] = features["breadth"].clip(upper=1.0)
    features["fund_inflow"] = features["fund_flow"] >= features["fund_flow"].median()
    features["trend20"] = 1
    features["consecutive_up"] = 2

    sector_panel = build_sector_panel(features)
    sector_panel = sector_base.drop(columns=["leader_contrib"]).join(sector_panel)
    sector_panel["data_quality"] = "seed_static"
    sector_panel["state_note"] = (
        "基于股票池静态结构生成；接入收盘行情后会替换为涨跌、成交额和资金流。 "
        + sector_panel["state_note"]
    )

    stock_panel = universe.merge(
        sector_panel[["strength", "strength_rank", "state", "state_note"]],
        left_on="sector",
        right_index=True,
        how="left",
    )
    stock_panel = stock_panel.rename(
        columns={
            "strength": "sector_strength",
            "strength_rank": "sector_strength_rank",
            "state": "sector_state",
            "state_note": "sector_state_note",
        }
    )
    stock_panel["is_top_leader"] = stock_panel["rank"] <= 3
    stock_panel["leader_badge"] = stock_panel["is_top_leader"].map(
        {True: "Top3 市值龙头", False: "板块中军观察"}
    )
    stock_panel = stock_panel.sort_values(["sector", "rank"]).reset_index(drop=True)
    return sector_panel, stock_panel


def stock_panel() -> pd.DataFrame:
    hit = cache.read("pipeline", "stock_panel", "latest")
    if hit is not None:
        return hit
    _, stocks = build_universe_panels()
    cache.write("pipeline", "stock_panel", "latest", stocks)
    return stocks


def refresh_eod() -> pd.DataFrame:
    hit = cache.read("pipeline", "sector_panel", "latest")
    required = {"stock_count", "top_leaders", "coverage", "state_note"}
    if hit is not None and required <= set(hit.columns):
        return hit.set_index("sector") if "sector" in hit.columns else hit

    panel, stocks = build_universe_panels()
    cache.write("pipeline", "sector_panel", "latest", panel.reset_index(names="sector"))
    cache.write("pipeline", "stock_panel", "latest", stocks)
    return panel
