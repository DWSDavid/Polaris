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


def _prepare_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["trade_date"] = out["trade_date"].astype(str)
    out = out.sort_values("trade_date").set_index("trade_date")
    return out
