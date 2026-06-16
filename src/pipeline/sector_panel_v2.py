"""Build the v2 Eastmoney sector panel."""

from __future__ import annotations

import pandas as pd

from src.compute import config, indicators
from src.compute.state_machine import classify_state
from src.compute.trend_v2 import streak_days, turning_point_flag
from src.data import em_client


def build_sector_panel_v2(
    industry_realtime: pd.DataFrame | None = None,
    flow_5d: pd.DataFrame | None = None,
    flow_10d: pd.DataFrame | None = None,
    histories: dict[str, pd.DataFrame] | None = None,
    leaders: pd.DataFrame | None = None,
) -> pd.DataFrame:
    realtime = (
        industry_realtime.copy()
        if industry_realtime is not None
        else em_client.industry_realtime()
    )
    flow_5d = flow_5d.copy() if flow_5d is not None else em_client.industry_fund_flow("5日")
    flow_10d = (
        flow_10d.copy() if flow_10d is not None else em_client.industry_fund_flow("10日")
    )
    histories = histories or {}

    panel = realtime.merge(
        _period_flow(flow_5d, "inflow_5d"), on="sector", how="left"
    ).merge(_period_flow(flow_10d, "inflow_10d"), on="sector", how="left")
    panel["inflow_5d"] = _num(panel, "inflow_5d").fillna(0.0)
    panel["inflow_10d"] = _num(panel, "inflow_10d").fillna(0.0)
    panel["main_net_inflow"] = _num(panel, "main_net_inflow").fillna(0.0)
    panel["pct_chg"] = _num(panel, "pct_chg").fillna(0.0)
    panel["amount"] = _num(panel, "amount").fillna(0.0)

    total_count = _num(panel, "up_count").fillna(0) + _num(panel, "down_count").fillna(0)
    panel["diffusion"] = _num(panel, "up_count").fillna(0).where(
        total_count > 0, 0
    ) / total_count.where(total_count > 0, 1)
    leader_names = panel["sector"].map(_top_leader_map(leaders))
    fallback_leaders = panel.get("leading_stock", pd.Series("", index=panel.index))
    panel["top_leaders"] = leader_names.fillna(fallback_leaders.fillna("")).values
    panel["leader_contrib"] = _leader_contrib(panel, leaders)

    trend_days = []
    turning_points = []
    volume_amp = []
    for row in panel.itertuples():
        hist = histories.get(row.sector, pd.DataFrame())
        trend_days.append(streak_days(hist.get("pct_chg", pd.Series(dtype=float))))
        turning_points.append(
            bool(
                turning_point_flag(
                    hist.get("main_net_inflow", pd.Series(dtype=float)),
                    hist.get("pct_chg", pd.Series(dtype=float)),
                )
            )
        )
        volume_amp.append(_volume_amp(hist, row.amount))
    panel["trend_days"] = trend_days
    panel["turning_point"] = pd.Series(turning_points, dtype=object)
    panel["volume_amp"] = volume_amp
    panel["fund_inflow"] = (panel["main_net_inflow"] > 0) | (panel["inflow_10d"] > 0)
    panel["trend20"] = panel["trend_days"].map(lambda value: 1 if value > 0 else (-1 if value < 0 else 0))
    panel["consecutive_up"] = panel["trend_days"].clip(lower=0)

    features = pd.DataFrame(index=panel.index)
    features["relative_return"] = panel["pct_chg"]
    features["volume_amp"] = panel["volume_amp"]
    features["fund_flow"] = panel["main_net_inflow"] + panel["inflow_10d"]
    features["breadth"] = panel["diffusion"]
    features["leader_contrib"] = panel["leader_contrib"]
    panel["strength"] = indicators.sector_strength(features, config.STRENGTH_WEIGHTS)
    panel["strength_rank"] = panel["strength"].rank(pct=True)
    panel["state"] = [
        classify_state(
            row.strength_rank,
            row.diffusion,
            row.fund_inflow,
            row.volume_amp,
            row.trend20,
            row.consecutive_up,
        )
        for row in panel.itertuples()
    ]
    panel["data_quality"] = "eastmoney_realtime"
    return panel.sort_values(
        ["strength_rank", "trend_days", "inflow_10d"],
        ascending=False,
    ).reset_index(drop=True)


def _period_flow(flow: pd.DataFrame, target: str) -> pd.DataFrame:
    if flow.empty:
        return pd.DataFrame(columns=["sector", target])
    return flow[["sector", "main_net_inflow"]].rename(
        columns={"main_net_inflow": target}
    )


def _top_leader_map(leaders: pd.DataFrame | None) -> pd.Series:
    if leaders is None or leaders.empty:
        return pd.Series(dtype=object)
    sorted_leaders = leaders.sort_values(["sector", "rank"], na_position="last")
    return sorted_leaders.groupby("sector")["name"].apply(
        lambda values: "、".join(values.dropna().astype(str).head(3))
    )


def _leader_contrib(panel: pd.DataFrame, leaders: pd.DataFrame | None) -> pd.Series:
    if leaders is None or leaders.empty or "amount" not in leaders.columns:
        return pd.Series(0.0, index=panel.index)
    leader_amount = (
        leaders.assign(amount=_num(leaders, "amount"))
        .sort_values(["sector", "rank"], na_position="last")
        .groupby("sector")["amount"]
        .apply(lambda values: values.head(3).sum())
    )
    mapped = panel["sector"].map(leader_amount).fillna(0.0)
    amount = _num(panel, "amount").replace(0, pd.NA)
    return (mapped / amount).fillna(0.0).clip(0, 1)


def _volume_amp(hist: pd.DataFrame, latest_amount: float) -> float:
    if hist is None or hist.empty or "amount" not in hist.columns:
        return 1.0
    amounts = _num(hist, "amount").dropna()
    if amounts.empty or amounts.mean() == 0:
        return 1.0
    return float(latest_amount / amounts.tail(20).mean())


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(pd.NA, index=frame.index, dtype="Float64")
    return pd.to_numeric(frame[column], errors="coerce")
