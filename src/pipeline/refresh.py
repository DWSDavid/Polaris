"""End-of-day orchestration helpers."""

from pathlib import Path
import argparse

import pandas as pd

from src.compute import config, indicators
from src.compute.decision_explain import enrich_decision_explanations
from src.compute.rotation_history import build_sector_history, build_stock_history
from src.compute.state_machine import classify_state
from src.compute.trend import consecutive_up_days, trend_sign
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


def build_universe_panels(
    path: Path = SEED_UNIVERSE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
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
    features["breadth"] = (
        sector_base["coverage"] / sector_base["coverage"].max()
    ).fillna(0)
    features["leader_contrib"] = sector_base["leader_contrib"].fillna(0)
    features["diffusion"] = features["breadth"].clip(upper=1.0)
    features["fund_inflow"] = features["fund_flow"] >= features["fund_flow"].median()
    features["trend20"] = 1
    features["consecutive_up"] = 2

    sector_panel = build_sector_panel(features)
    sector_panel = sector_base.drop(columns=["leader_contrib"]).join(sector_panel)
    sector_panel["data_quality"] = "seed_static"
    sector_panel["signals_confirmed"] = False
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
    stock_panel["signals_confirmed"] = False
    stock_panel["leader_badge"] = stock_panel["is_top_leader"].map(
        {True: "Top3 市值龙头", False: "板块中军观察"}
    )
    stock_panel = stock_panel.sort_values(["sector", "rank"]).reset_index(drop=True)
    sector_panel, stock_panel = enrich_decision_explanations(sector_panel, stock_panel)
    return sector_panel, stock_panel


def _latest_row(frame: pd.DataFrame | None) -> dict:
    if frame is None or frame.empty:
        return {}
    if "trade_date" in frame.columns:
        frame = frame.sort_values("trade_date")
    return frame.iloc[-1].to_dict()


def enrich_stock_panel_with_market_data(
    stocks: pd.DataFrame,
    daily_by_symbol: dict[str, pd.DataFrame],
    basic_by_symbol: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    basic_by_symbol = basic_by_symbol or {}
    rows = []
    for row in stocks.to_dict("records"):
        symbol = row["symbol"]
        daily_frame = daily_by_symbol.get(symbol)
        if (
            daily_frame is not None
            and not daily_frame.empty
            and "trade_date" in daily_frame.columns
        ):
            daily_frame = daily_frame.sort_values("trade_date")
        daily = _latest_row(daily_frame)
        basic = _latest_row(basic_by_symbol.get(symbol))
        row.update(
            {
                "trade_date": daily.get("trade_date") or basic.get("trade_date"),
                "latest_close": daily.get("close"),
                "pct_chg": daily.get("pct_chg", daily.get("pct")),
                "amount": daily.get("amount"),
                "turnover_rate": basic.get("turnover_rate"),
                "volume_ratio": basic.get("volume_ratio"),
                "pe_ttm": basic.get("pe_ttm"),
                "pb": basic.get("pb"),
                "total_mv": basic.get("total_mv"),
                "circ_mv": basic.get("circ_mv"),
            }
        )
        if daily_frame is not None and not daily_frame.empty:
            row["trend20"] = trend_sign(
                daily_frame.get("close", pd.Series(dtype=float))
            )
            row["consecutive_up"] = consecutive_up_days(
                daily_frame.get(
                    "pct_chg", daily_frame.get("pct", pd.Series(dtype=float))
                )
            )
        else:
            row["trend20"] = 0
            row["consecutive_up"] = 0
        row["market_data_available"] = pd.notna(row["latest_close"]) or pd.notna(
            row["pct_chg"]
        )
        row["signals_confirmed"] = bool(row["market_data_available"])
        rows.append(row)
    return pd.DataFrame(rows)


def normalize_akshare_daily(raw: pd.DataFrame) -> pd.DataFrame:
    out = raw.copy()
    if "date" in out.columns:
        out["trade_date"] = pd.to_datetime(out["date"]).dt.strftime("%Y%m%d")
    elif "日期" in out.columns:
        out["trade_date"] = pd.to_datetime(out["日期"]).dt.strftime("%Y%m%d")
    if "pct" in out.columns:
        out["pct_chg"] = out["pct"]
    elif "涨跌幅" in out.columns:
        out["pct_chg"] = out["涨跌幅"]
    if "成交额" in out.columns and "amount" not in out.columns:
        out["amount"] = out["成交额"]
    if "收盘" in out.columns and "close" not in out.columns:
        out["close"] = out["收盘"]
    return out[["trade_date", "close", "pct_chg", "amount"]]


def akshare_daily_fetcher(symbol: str, start: str, end: str) -> pd.DataFrame:
    from src.data.akshare_client import daily_hist

    return normalize_akshare_daily(daily_hist(symbol, start, end))


def akshare_fund_flow_fetcher(symbol: str, start: str, end: str) -> pd.DataFrame:
    from src.data.akshare_client import individual_fund_flow

    return individual_fund_flow(symbol)


def empty_basic_fetcher(symbol: str, start: str, end: str) -> pd.DataFrame:
    return pd.DataFrame()


def provider_fetchers(provider: str):
    if provider == "akshare":
        return akshare_daily_fetcher, empty_basic_fetcher
    if provider == "tushare":
        from src.data import tushare_client

        return tushare_client.daily, tushare_client.daily_basic
    raise ValueError(f"Unsupported provider: {provider}")


MAIN_INFLOW_COLUMNS = (
    "主力净流入-净额",
    "主力净流入净额",
    "main_net_inflow",
)


def _latest_main_inflow(frame: pd.DataFrame | None) -> float | None:
    if frame is None or frame.empty:
        return None
    for column in MAIN_INFLOW_COLUMNS:
        if column in frame.columns:
            values = pd.to_numeric(frame[column], errors="coerce").dropna()
            if not values.empty:
                return float(values.iloc[-1])
    return None


def aggregate_main_inflow(
    stocks: pd.DataFrame,
    flows_by_symbol: dict[str, pd.DataFrame],
) -> dict[str, float]:
    totals: dict[str, float] = {}
    for stock in stocks[["symbol", "sector"]].to_dict("records"):
        value = _latest_main_inflow(flows_by_symbol.get(stock["symbol"]))
        if value is None:
            continue
        totals[stock["sector"]] = totals.get(stock["sector"], 0.0) + value
    return totals


def build_market_sector_panel(
    stocks: pd.DataFrame,
    main_inflow_by_sector: dict[str, float] | None = None,
) -> pd.DataFrame:
    main_inflow_by_sector = main_inflow_by_sector or {}

    def trend_from_group(group: pd.DataFrame) -> int:
        if "trend20" not in group.columns:
            return 0
        value = pd.to_numeric(group["trend20"], errors="coerce").fillna(0).mean()
        if value > 0:
            return 1
        if value < 0:
            return -1
        return 0

    def signed_flow(group: pd.DataFrame) -> float:
        amount = group["amount"].fillna(0)
        signed = amount.where(
            group["pct_chg"] > 0, -amount.where(group["pct_chg"] < 0, 0)
        )
        total = signed.sum()
        if total > 0:
            return 1.0
        if total < 0:
            return -1.0
        return 0.0

    grouped = stocks.groupby("sector", sort=True)
    sector_base = grouped.agg(
        stock_count=("name", "count"),
        total_market_cap=("market_cap", "sum"),
        avg_pct_chg=("pct_chg", "mean"),
        amount=("amount", "sum"),
        volume_amp=("volume_ratio", "mean"),
        coverage=("sector_share", "sum"),
    )
    sector_base["top_leaders"] = grouped.apply(
        lambda g: "、".join(g.sort_values("rank").head(3)["name"].tolist()),
        include_groups=False,
    )
    sector_base["diffusion"] = grouped["pct_chg"].apply(
        lambda s: float((s > 0).sum() / s.notna().sum()) if s.notna().sum() else 0.0
    )
    sector_base["leader_contrib"] = grouped.apply(
        lambda g: (
            float(
                g.sort_values("rank").head(3)["amount"].fillna(0).sum()
                / g["amount"].fillna(0).sum()
            )
            if g["amount"].fillna(0).sum() > 0
            else 0.0
        ),
        include_groups=False,
    )
    sector_base["fund_flow"] = grouped.apply(signed_flow, include_groups=False)
    for sector, value in main_inflow_by_sector.items():
        if sector in sector_base.index:
            sector_base.loc[sector, "fund_flow"] = value
    sector_base["trend20"] = grouped.apply(trend_from_group, include_groups=False)
    if "consecutive_up" in stocks.columns:
        sector_base["consecutive_up"] = (
            grouped["consecutive_up"].median().fillna(0).round().astype(int)
        )
    else:
        sector_base["consecutive_up"] = 0

    features = pd.DataFrame(index=sector_base.index)
    features["relative_return"] = sector_base["avg_pct_chg"].fillna(0)
    features["volume_amp"] = sector_base["volume_amp"].fillna(1.0)
    features["fund_flow"] = sector_base["fund_flow"]
    features["breadth"] = sector_base["diffusion"]
    features["leader_contrib"] = sector_base["leader_contrib"]
    features["diffusion"] = sector_base["diffusion"]
    features["fund_inflow"] = sector_base["fund_flow"] > 0
    features["trend20"] = sector_base["trend20"]
    features["consecutive_up"] = sector_base["consecutive_up"]

    panel = build_sector_panel(features)
    panel = sector_base.drop(
        columns=[
            "leader_contrib",
            "fund_flow",
            "volume_amp",
            "diffusion",
            "trend20",
            "consecutive_up",
        ]
    ).join(panel)
    panel["data_quality"] = "market_snapshot"
    panel["signals_confirmed"] = True
    return panel


def stock_panel() -> pd.DataFrame:
    hit = cache.read("pipeline", "stock_panel", "latest")
    if hit is not None:
        return hit
    _, stocks = build_universe_panels()
    cache.write("pipeline", "stock_panel", "latest", stocks)
    return stocks


def sector_history_panel() -> pd.DataFrame:
    hit = cache.read("pipeline", "sector_history", "latest")
    if hit is not None:
        return hit
    return pd.DataFrame()


def stock_history_panel() -> pd.DataFrame:
    hit = cache.read("pipeline", "stock_history", "latest")
    if hit is not None:
        return hit
    return pd.DataFrame()


def _fetch_market_data(
    stocks: pd.DataFrame, start: str, end: str, daily_fetcher, basic_fetcher
):
    daily_by_symbol = {}
    basic_by_symbol = {}
    for symbol in stocks["symbol"]:
        try:
            daily_by_symbol[symbol] = daily_fetcher(symbol, start, end)
        except Exception:
            daily_by_symbol[symbol] = pd.DataFrame()
        try:
            basic_by_symbol[symbol] = basic_fetcher(symbol, start, end)
        except Exception:
            basic_by_symbol[symbol] = pd.DataFrame()
    return daily_by_symbol, basic_by_symbol


def _fetch_fund_flows(stocks: pd.DataFrame, start: str, end: str, fund_flow_fetcher):
    flows_by_symbol = {}
    if fund_flow_fetcher is None:
        return flows_by_symbol
    for symbol in stocks["symbol"]:
        try:
            flows_by_symbol[symbol] = fund_flow_fetcher(symbol, start, end)
        except Exception:
            flows_by_symbol[symbol] = pd.DataFrame()
    return flows_by_symbol


def refresh_eod(
    start: str | None = None,
    end: str | None = None,
    force_market: bool = False,
    daily_fetcher=None,
    basic_fetcher=None,
    fund_flow_fetcher=None,
    limit: int | None = None,
) -> pd.DataFrame:
    hit = cache.read("pipeline", "sector_panel", "latest")
    should_market = (
        force_market
        or daily_fetcher is not None
        or basic_fetcher is not None
        or fund_flow_fetcher is not None
    )
    required = {
        "stock_count",
        "top_leaders",
        "coverage",
        "state_note",
        "risk_level",
        "action_hint",
        "watch_points",
        "signals_confirmed",
    }
    if not should_market and hit is not None and required <= set(hit.columns):
        return hit.set_index("sector") if "sector" in hit.columns else hit

    panel, stocks = build_universe_panels()
    if should_market:
        if start is None or end is None:
            raise ValueError("start and end are required when refreshing market data")
        if daily_fetcher is None or basic_fetcher is None:
            default_daily, default_basic = provider_fetchers("akshare")
            daily_fetcher = daily_fetcher or default_daily
            basic_fetcher = basic_fetcher or default_basic
        if limit is not None:
            stocks = stocks.head(limit).copy()
        daily_by_symbol, basic_by_symbol = _fetch_market_data(
            stocks,
            start,
            end,
            daily_fetcher,
            basic_fetcher,
        )
        stocks = enrich_stock_panel_with_market_data(
            stocks,
            daily_by_symbol,
            basic_by_symbol,
        )
        sector_history = build_sector_history(stocks, daily_by_symbol)
        stock_history = build_stock_history(stocks, daily_by_symbol)
        if stocks["market_data_available"].any():
            flows_by_symbol = _fetch_fund_flows(stocks, start, end, fund_flow_fetcher)
            main_inflow_by_sector = aggregate_main_inflow(stocks, flows_by_symbol)
            panel = build_market_sector_panel(stocks, main_inflow_by_sector)
            stocks = stocks.merge(
                panel[["strength", "strength_rank", "state", "state_note"]],
                left_on="sector",
                right_index=True,
                how="left",
                suffixes=("", "_market"),
            )
            stocks["sector_strength"] = stocks["strength"]
            stocks["sector_strength_rank"] = stocks["strength_rank"]
            stocks["sector_state"] = stocks["state"]
            stocks["sector_state_note"] = stocks["state_note"]
            stocks = stocks.drop(
                columns=["strength", "strength_rank", "state", "state_note"]
            )
            panel, stocks = enrich_decision_explanations(panel, stocks)
        else:
            panel, stocks = build_universe_panels()
            sector_history = pd.DataFrame()
            stock_history = pd.DataFrame()

    cache.write("pipeline", "sector_panel", "latest", panel.reset_index(names="sector"))
    cache.write("pipeline", "stock_panel", "latest", stocks)
    if "sector_history" in locals() and not sector_history.empty:
        cache.write("pipeline", "sector_history", "latest", sector_history)
    if "stock_history" in locals() and not stock_history.empty:
        cache.write("pipeline", "stock_history", "latest", stock_history)
    return panel


def run_refresh(
    provider: str, start: str, end: str, limit: int | None = None
) -> pd.DataFrame:
    daily_fetcher, basic_fetcher = provider_fetchers(provider)
    fund_flow_fetcher = akshare_fund_flow_fetcher if provider == "akshare" else None
    return refresh_eod(
        start=start,
        end=end,
        force_market=True,
        daily_fetcher=daily_fetcher,
        basic_fetcher=basic_fetcher,
        fund_flow_fetcher=fund_flow_fetcher,
        limit=limit,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh Polaris EOD panels.")
    parser.add_argument("--provider", choices=["akshare", "tushare"], default="akshare")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    panel = run_refresh(args.provider, args.start, args.end, args.limit)
    print(
        f"refreshed provider={args.provider} sectors={len(panel)} "
        f"data_quality={panel['data_quality'].iloc[0]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
