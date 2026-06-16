"""Three-month sector rotation timeline assembly."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from src.data import em_client


def build_rotation_timeline(hist: pd.DataFrame) -> pd.DataFrame:
    if hist.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "sector",
                "pct_chg",
                "amount",
                "main_net_inflow",
                "strength",
                "rank",
            ]
        )

    frame = hist.copy()
    if "date" not in frame.columns and "trade_date" in frame.columns:
        frame["date"] = frame["trade_date"]
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    frame["pct_chg"] = pd.to_numeric(frame.get("pct_chg"), errors="coerce").fillna(0.0)
    frame["amount"] = pd.to_numeric(frame.get("amount"), errors="coerce").fillna(0.0)
    frame["main_net_inflow"] = pd.to_numeric(
        frame.get("main_net_inflow"), errors="coerce"
    ).fillna(0.0)
    frame = frame.dropna(subset=["date", "sector"]).copy()
    if frame.empty:
        return build_rotation_timeline(pd.DataFrame())

    flow_yi = frame["main_net_inflow"] / 100_000_000
    amount_yi = frame["amount"] / 100_000_000
    frame["strength"] = (
        frame["pct_chg"] * 1.4
        + flow_yi.clip(lower=-50, upper=50) * 0.18
        + amount_yi.rank(pct=True).fillna(0) * 2.0
    )
    frame["rank"] = frame.groupby("date")["strength"].rank(
        method="first", ascending=False
    ).astype(int)
    return frame[
        [
            "date",
            "sector",
            "pct_chg",
            "amount",
            "main_net_inflow",
            "strength",
            "rank",
        ]
    ].sort_values(["date", "rank"]).reset_index(drop=True)


def weekly_rank(timeline: pd.DataFrame) -> pd.DataFrame:
    if timeline.empty:
        return pd.DataFrame(
            columns=[
                "week",
                "sector",
                "strength",
                "main_net_inflow",
                "rank",
            ]
        )
    frame = timeline.copy()
    frame["date_dt"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date_dt", "sector"]).copy()
    frame["week"] = frame["date_dt"].dt.strftime("%G-%V")
    grouped = (
        frame.groupby(["week", "sector"], as_index=False)
        .agg(
            strength=("strength", "mean"),
            main_net_inflow=("main_net_inflow", "sum"),
            pct_chg=("pct_chg", "sum"),
        )
    )
    grouped["rank"] = grouped.groupby("week")["strength"].rank(
        method="first", ascending=False
    ).astype(int)
    return grouped.sort_values(["week", "rank"]).reset_index(drop=True)


def leader_changes(weekly: pd.DataFrame) -> dict:
    if weekly.empty:
        return {"leaders": [], "path": "", "segments": [], "summary": "暂无轮动样本。"}

    top = weekly.loc[weekly["rank"] == 1].sort_values("week")
    leaders: list[str] = []
    segments: list[dict] = []
    for item in top.to_dict("records"):
        sector = str(item.get("sector", ""))
        week = str(item.get("week", ""))
        if not leaders or leaders[-1] != sector:
            leaders.append(sector)
            segments.append(
                {
                    "sector": sector,
                    "start_week": week,
                    "end_week": week,
                    "strength": float(item.get("strength", 0) or 0),
                }
            )
        else:
            segments[-1]["end_week"] = week
            segments[-1]["strength"] = float(item.get("strength", 0) or 0)

    path = "→".join(leaders)
    summary = f"过去窗口的领涨路径：{path}。" if path else "暂无轮动样本。"
    return {"leaders": leaders, "path": path, "segments": segments, "summary": summary}


def fetch_rotation_timeline(days: int = 90, max_sectors: int = 60) -> pd.DataFrame:
    realtime = em_client.industry_realtime()
    if realtime.empty:
        return build_rotation_timeline(pd.DataFrame())
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    sectors = (
        realtime.sort_values(["amount", "pct_chg"], ascending=False)["sector"]
        .dropna()
        .astype(str)
        .head(max_sectors)
        .tolist()
    )
    rows = []
    for sector in sectors:
        try:
            hist = em_client.industry_hist(sector, start, end)
            flow = em_client.industry_fund_flow_hist(sector)
        except Exception:
            continue
        if hist.empty:
            continue
        frame = hist.copy()
        if not flow.empty and "main_net_inflow" in flow.columns:
            frame = frame.merge(
                flow[["trade_date", "main_net_inflow"]],
                on="trade_date",
                how="left",
            )
        if "main_net_inflow" not in frame.columns:
            frame["main_net_inflow"] = 0.0
        frame["sector"] = sector
        rows.append(frame)
    hist_all = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    return build_rotation_timeline(hist_all)
