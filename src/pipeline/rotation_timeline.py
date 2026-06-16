"""Three-month sector rotation timeline assembly."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from src.data import cache, em_client


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
    default_end = datetime.now().strftime("%Y%m%d")
    default_start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    candidate_limit = min(len(realtime), max(max_sectors * 4, max_sectors + 20))
    sectors = (
        realtime.sort_values(["amount", "pct_chg"], ascending=False)["sector"]
        .dropna()
        .astype(str)
        .head(candidate_limit)
        .tolist()
    )
    rows = []
    has_hist_cache = _has_industry_hist_cache()
    for sector in sectors:
        hist = _cached_industry_hist(sector, days)
        flow = _cached_industry_flow(sector)
        if hist.empty and has_hist_cache:
            continue
        if hist.empty:
            try:
                flow = em_client.industry_fund_flow_hist(sector)
            except Exception:
                flow = pd.DataFrame()

            start, end = _window_from_flow(flow, days, default_start, default_end)
            try:
                hist = em_client.industry_hist(sector, start, end)
            except Exception:
                hist = pd.DataFrame()
            if hist.empty and (start, end) != (default_start, default_end):
                try:
                    hist = em_client.industry_hist(sector, default_start, default_end)
                except Exception:
                    hist = pd.DataFrame()
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
        if len(rows) >= max_sectors:
            break
    hist_all = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    return build_rotation_timeline(hist_all)


def _has_industry_hist_cache() -> bool:
    hist_dir = cache.CACHE_DIR / em_client.CACHE_SOURCE / "industry_hist"
    return hist_dir.exists() and any(hist_dir.glob("*.parquet"))


def _window_from_flow(
    flow: pd.DataFrame, days: int, default_start: str, default_end: str
) -> tuple[str, str]:
    if flow.empty or "trade_date" not in flow.columns:
        return default_start, default_end
    dates = pd.to_datetime(flow["trade_date"], errors="coerce").dropna()
    if dates.empty:
        return default_start, default_end
    end_dt = dates.max()
    start_dt = end_dt - timedelta(days=days)
    return start_dt.strftime("%Y%m%d"), end_dt.strftime("%Y%m%d")


def _cached_industry_hist(sector: str, days: int) -> pd.DataFrame:
    hist_dir = cache.CACHE_DIR / em_client.CACHE_SOURCE / "industry_hist"
    if not hist_dir.exists():
        return pd.DataFrame()
    sector_key = em_client._safe_key(sector)
    candidates = sorted(hist_dir.glob(f"{sector_key}_*.parquet"), reverse=True)
    for path in candidates:
        try:
            hist = pd.read_parquet(path)
        except Exception:
            continue
        if hist.empty or "trade_date" not in hist.columns:
            continue
        hist = hist.copy()
        dates = pd.to_datetime(hist["trade_date"], errors="coerce")
        if dates.notna().any():
            cutoff = dates.max() - timedelta(days=days)
            hist = hist.loc[dates >= cutoff].copy()
        return hist
    return pd.DataFrame()


def _cached_industry_flow(sector: str) -> pd.DataFrame:
    flow_dir = cache.CACHE_DIR / em_client.CACHE_SOURCE / "industry_fund_flow_hist"
    if not flow_dir.exists():
        return pd.DataFrame()
    path = flow_dir / f"{em_client._safe_key(sector)}.parquet"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()
