"""Historical sector rotation tracking from stock daily series."""

from __future__ import annotations

import pandas as pd


def build_sector_history(
    stocks: pd.DataFrame,
    daily_by_symbol: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    stock_history = build_stock_history(stocks, daily_by_symbol)
    if stock_history.empty:
        return pd.DataFrame(
            columns=[
                "trade_date",
                "sector",
                "avg_pct_chg",
                "amount",
                "fund_flow",
                "diffusion",
                "stock_count",
                "positive_count",
                "leader_amount",
                "leader_contrib",
            ]
        )
    grouped = stock_history.groupby(["trade_date", "sector"], sort=True)
    history = grouped.apply(_aggregate_sector_day, include_groups=False).reset_index()
    return history.sort_values(["sector", "trade_date"]).reset_index(drop=True)


def build_stock_history(
    stocks: pd.DataFrame,
    daily_by_symbol: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows = []
    stock_lookup = stocks.set_index("symbol")
    for symbol, daily in daily_by_symbol.items():
        if symbol not in stock_lookup.index or daily is None or daily.empty:
            continue
        stock = stock_lookup.loc[symbol]
        frame = daily.copy()
        if "trade_date" not in frame.columns:
            continue
        frame["trade_date"] = frame["trade_date"].astype(str)
        frame["pct_chg"] = pd.to_numeric(frame.get("pct_chg"), errors="coerce")
        frame["amount"] = pd.to_numeric(frame.get("amount"), errors="coerce")
        frame["symbol"] = symbol
        frame["sector"] = stock["sector"]
        frame["name"] = stock["name"]
        frame["rank"] = stock["rank"]
        columns = [
            "trade_date",
            "sector",
            "symbol",
            "name",
            "rank",
            "close",
            "pct_chg",
            "amount",
        ]
        rows.append(frame[[column for column in columns if column in frame.columns]])
    if not rows:
        return pd.DataFrame(
            columns=[
                "trade_date",
                "sector",
                "symbol",
                "name",
                "rank",
                "close",
                "pct_chg",
                "amount",
            ]
        )
    return pd.concat(rows, ignore_index=True).sort_values(
        ["sector", "rank", "trade_date"]
    )


def summarize_sector_track(
    history: pd.DataFrame,
    short_window: int = 5,
    mid_window: int = 15,
) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame(
            columns=[
                "sector",
                f"fund_flow_{short_window}d",
                f"fund_flow_{mid_window}d",
                f"positive_days_{mid_window}d",
                "current_positive_streak",
                "latest_diffusion",
                "track_label",
            ]
        )
    rows = []
    for sector, group in history.sort_values("trade_date").groupby("sector", sort=True):
        short = group.tail(short_window)
        mid = group.tail(mid_window)
        row = {
            "sector": sector,
            f"fund_flow_{short_window}d": float(short["fund_flow"].fillna(0).sum()),
            f"fund_flow_{mid_window}d": float(mid["fund_flow"].fillna(0).sum()),
            f"positive_days_{mid_window}d": int(
                (mid["avg_pct_chg"].fillna(0) > 0).sum()
            ),
            "current_positive_streak": _positive_streak(group["avg_pct_chg"]),
            "latest_diffusion": float(group.iloc[-1]["diffusion"]),
        }
        row["track_label"] = _track_label(
            row[f"fund_flow_{short_window}d"],
            row[f"positive_days_{mid_window}d"],
            row["current_positive_streak"],
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        [f"fund_flow_{short_window}d", "current_positive_streak"],
        ascending=False,
    )


def summarize_flow_rotation(flow_history: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    if flow_history.empty:
        return pd.DataFrame(
            columns=[
                "sector",
                f"flow_{window}d",
                "latest_flow",
                "flow_delta",
                "rotation_rank",
                "rotation_label",
            ]
        )
    history = flow_history.copy()
    history["trade_date"] = history["trade_date"].astype(str)
    history["main_net_inflow"] = pd.to_numeric(
        history["main_net_inflow"], errors="coerce"
    ).fillna(0.0)
    rows = []
    for sector, group in history.sort_values("trade_date").groupby("sector", sort=True):
        recent = group.tail(window)
        split = max(1, len(recent) // 2)
        first_half = recent.head(split)["main_net_inflow"].sum()
        second_half = recent.tail(max(1, len(recent) - split))["main_net_inflow"].sum()
        total = float(recent["main_net_inflow"].sum())
        delta = float(second_half - first_half)
        rows.append(
            {
                "sector": sector,
                f"flow_{window}d": total,
                "latest_flow": float(recent.iloc[-1]["main_net_inflow"]),
                "flow_delta": delta,
                "rotation_label": _rotation_label(total, delta),
            }
        )
    out = pd.DataFrame(rows).sort_values(
        [f"flow_{window}d", "flow_delta"], ascending=False
    )
    out["rotation_rank"] = range(1, len(out) + 1)
    return out.reset_index(drop=True)


def build_rotation_chain(flow_history: pd.DataFrame, top_n: int = 1) -> dict:
    if flow_history.empty:
        return {"leaders": [], "path": "", "summary": "资金接力样本不足。"}
    history = flow_history.copy()
    history["trade_date"] = history["trade_date"].astype(str)
    history["main_net_inflow"] = pd.to_numeric(
        history["main_net_inflow"], errors="coerce"
    ).fillna(0.0)
    leaders = []
    for _, group in history.sort_values("trade_date").groupby("trade_date", sort=True):
        top = group.sort_values("main_net_inflow", ascending=False).head(top_n)
        for sector in top["sector"].dropna().astype(str):
            if not leaders or leaders[-1] != sector:
                leaders.append(sector)
    path = "→".join(leaders)
    if len(leaders) <= 1:
        summary = f"资金仍集中在{leaders[0]}。" if leaders else "资金接力样本不足。"
    else:
        summary = f"资金接力路径：{path}。观察新接力方向是否继续扩散。"
    return {"leaders": leaders, "path": path, "summary": summary}


def _aggregate_sector_day(group: pd.DataFrame) -> pd.Series:
    amount = group["amount"].fillna(0)
    signed_amount = amount.where(
        group["pct_chg"] > 0,
        -amount.where(group["pct_chg"] < 0, 0),
    )
    leader_amount = group[group["rank"] <= 3]["amount"].fillna(0).sum()
    total_amount = amount.sum()
    positive_count = int((group["pct_chg"] > 0).sum())
    stock_count = int(group["pct_chg"].notna().sum())
    return pd.Series(
        {
            "avg_pct_chg": float(group["pct_chg"].mean()),
            "amount": float(total_amount),
            "fund_flow": float(signed_amount.sum()),
            "diffusion": float(positive_count / stock_count) if stock_count else 0.0,
            "stock_count": stock_count,
            "positive_count": positive_count,
            "leader_amount": float(leader_amount),
            "leader_contrib": (
                float(leader_amount / total_amount) if total_amount else 0.0
            ),
        }
    )


def _positive_streak(values: pd.Series) -> int:
    total = 0
    for value in reversed(pd.to_numeric(values, errors="coerce").dropna().tolist()):
        if value <= 0:
            break
        total += 1
    return total


def _track_label(short_flow: float, positive_days: int, streak: int) -> str:
    if short_flow > 0 and streak >= 2:
        return "资金延续流入"
    if short_flow < 0 and positive_days <= 1:
        return "持续承压"
    if short_flow < 0:
        return "资金转弱"
    return "观察确认"


def _rotation_label(total_flow: float, flow_delta: float) -> str:
    if total_flow <= 0 and flow_delta < 0:
        return "资金转弱流出"
    if total_flow > 0 and flow_delta > 0:
        return "资金接力流入"
    if total_flow > 0:
        return "资金仍在流入"
    if total_flow < 0:
        return "资金边际修复"
    return "资金中性"
