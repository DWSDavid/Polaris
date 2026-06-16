"""Leader-to-sector linkage statistics."""

import pandas as pd


def detect_leader_events(
    daily: pd.DataFrame,
    pct_threshold: float = 3.0,
    volume_threshold: float = 1.5,
) -> pd.DataFrame:
    required = daily.copy()
    if "volume_ratio" not in required.columns:
        required["volume_ratio"] = 0.0
    mask = (required["pct_chg"] >= pct_threshold) & (
        required["volume_ratio"] >= volume_threshold
    )
    return required.loc[mask].reset_index(drop=True)


def forward_excess_returns(
    event_dates: list[str],
    sector_daily: pd.DataFrame,
    benchmark_daily: pd.DataFrame,
    horizons: list[int],
) -> pd.DataFrame:
    sector = _prepare_price_frame(sector_daily)
    benchmark = _prepare_price_frame(benchmark_daily)
    rows = []
    for event_date in event_dates:
        if event_date not in sector.index or event_date not in benchmark.index:
            continue
        sector_pos = sector.index.get_loc(event_date)
        benchmark_pos = benchmark.index.get_loc(event_date)
        row = {"event_date": event_date}
        for horizon in horizons:
            if sector_pos + horizon >= len(sector) or benchmark_pos + horizon >= len(benchmark):
                row[f"t{horizon}_excess"] = None
                continue
            sector_return = (
                sector.iloc[sector_pos + horizon]["close"] / sector.iloc[sector_pos]["close"]
            )
            benchmark_return = (
                benchmark.iloc[benchmark_pos + horizon]["close"]
                / benchmark.iloc[benchmark_pos]["close"]
            )
            row[f"t{horizon}_excess"] = sector_return - benchmark_return
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_linkage_stats(events: pd.DataFrame, horizons: list[int]) -> dict:
    summary = {"event_count": len(events)}
    for horizon in horizons:
        column = f"t{horizon}_excess"
        values = events[column].dropna()
        summary[f"t{horizon}_avg_excess"] = float(values.mean()) if len(values) else 0.0
        summary[f"t{horizon}_win_rate"] = float((values > 0).mean()) if len(values) else 0.0
    return summary


def leader_linkage_report(
    leader_daily: pd.DataFrame,
    sector_daily: pd.DataFrame,
    benchmark_daily: pd.DataFrame | None = None,
    horizons: list[int] | None = None,
    pct_threshold: float = 3.0,
    volume_threshold: float = 1.5,
) -> dict:
    horizons = horizons or [1, 3, 5]
    events = detect_leader_events(
        leader_daily,
        pct_threshold=pct_threshold,
        volume_threshold=volume_threshold,
    )
    if events.empty:
        return {
            "event_count": 0,
            "label": "样本不足",
            "summary": "龙头放量事件不足，暂时不能验证板块联动。",
        }

    event_dates = events["trade_date"].astype(str).tolist()
    benchmark = benchmark_daily if benchmark_daily is not None else _flat_benchmark(sector_daily)
    forward = forward_excess_returns(event_dates, sector_daily, benchmark, horizons)
    summary = summarize_linkage_stats(forward, horizons)
    label = _linkage_label(summary, horizons)
    summary["label"] = label
    summary["summary"] = _linkage_summary(summary, horizons)
    return summary


def _prepare_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["trade_date"] = out["trade_date"].astype(str)
    out = out.sort_values("trade_date").set_index("trade_date")
    return out


def _flat_benchmark(sector_daily: pd.DataFrame) -> pd.DataFrame:
    if sector_daily.empty:
        return pd.DataFrame(columns=["trade_date", "close"])
    out = sector_daily[["trade_date"]].copy()
    out["close"] = 1.0
    return out


def _linkage_label(summary: dict, horizons: list[int]) -> str:
    if summary.get("event_count", 0) <= 0:
        return "样本不足"
    preferred = 3 if 3 in horizons else horizons[min(1, len(horizons) - 1)]
    win_rate = summary.get(f"t{preferred}_win_rate", 0.0)
    avg = summary.get(f"t{preferred}_avg_excess", 0.0)
    if win_rate >= 0.55 and avg > 0:
        return "联动确认"
    if win_rate <= 0.45 and avg <= 0:
        return "单股脉冲"
    return "观察确认"


def _linkage_summary(summary: dict, horizons: list[int]) -> str:
    preferred = 3 if 3 in horizons else horizons[min(1, len(horizons) - 1)]
    win_rate = summary.get(f"t{preferred}_win_rate", 0.0)
    avg = summary.get(f"t{preferred}_avg_excess", 0.0)
    return (
        f"龙头放量后样本 {summary.get('event_count', 0)} 次，"
        f"T+{preferred} 胜率 {win_rate:.0%}，平均板块后续表现 {avg:.2%}，"
        f"结论：{summary.get('label')}。"
    )
