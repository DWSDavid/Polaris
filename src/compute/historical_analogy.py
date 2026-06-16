"""Historical analogies for "how much longer can this trend run?"."""

from __future__ import annotations

import pandas as pd


def build_analogy_samples(
    history: pd.DataFrame,
    horizons: tuple[int, ...] = (3, 5),
    max_lookahead: int = 10,
) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame()
    required = {"sector", "trade_date", "state", "trend_days", "close", "pct_chg"}
    missing = required - set(history.columns)
    if missing:
        raise ValueError(f"history missing columns: {sorted(missing)}")

    rows = []
    for _, group in history.sort_values("trade_date").groupby("sector", sort=False):
        ordered = group.reset_index(drop=True).copy()
        ordered["close"] = pd.to_numeric(ordered["close"], errors="coerce")
        ordered["pct_chg"] = pd.to_numeric(ordered["pct_chg"], errors="coerce")
        for index, row in ordered.iterrows():
            close = row["close"]
            if pd.isna(close) or close == 0:
                continue
            sample = {
                "sector": row["sector"],
                "trade_date": str(row["trade_date"]),
                "state": row["state"],
                "trend_days": int(row["trend_days"] or 0),
                "remaining_positive_days": _remaining_positive_days(
                    ordered["pct_chg"], index, max_lookahead
                ),
            }
            for horizon in horizons:
                future = ordered.iloc[index + 1 : index + horizon + 1]
                close_col = future["close"].dropna()
                if len(close_col) < horizon:
                    sample[f"forward_return_{horizon}d"] = pd.NA
                    sample[f"max_drawdown_{horizon}d"] = pd.NA
                    continue
                sample[f"forward_return_{horizon}d"] = float(close_col.iloc[-1] / close - 1)
                sample[f"max_drawdown_{horizon}d"] = _max_drawdown(close_col, close)
            rows.append(sample)
    return pd.DataFrame(rows)


def analogy_report(
    samples: pd.DataFrame,
    state: str,
    trend_days: int,
    tolerance: int = 1,
) -> dict:
    if samples.empty:
        return _empty_report(state, trend_days)
    matched = samples[
        (samples["state"].astype(str) == str(state))
        & (
            pd.to_numeric(samples["trend_days"], errors="coerce")
            .sub(int(trend_days))
            .abs()
            <= tolerance
        )
    ].copy()
    if matched.empty:
        return _empty_report(state, trend_days)

    report = {
        "state": state,
        "trend_days": int(trend_days),
        "sample_count": int(len(matched)),
        "median_remaining_positive_days": _median(
            matched.get("remaining_positive_days", pd.Series(dtype=float))
        ),
    }
    for horizon in _horizons_from_columns(matched, "forward_return_"):
        values = pd.to_numeric(matched[f"forward_return_{horizon}d"], errors="coerce")
        report[f"median_forward_return_{horizon}d"] = _median(values)
        report[f"win_rate_{horizon}d"] = _win_rate(values)
    for horizon in _horizons_from_columns(matched, "max_drawdown_"):
        values = pd.to_numeric(matched[f"max_drawdown_{horizon}d"], errors="coerce")
        report[f"median_max_drawdown_{horizon}d"] = _median(values)
    report["summary"] = _summary(report)
    return report


def _remaining_positive_days(values: pd.Series, index: int, max_lookahead: int) -> int:
    total = 0
    future = values.iloc[index + 1 : index + max_lookahead + 1]
    for value in future:
        if pd.isna(value) or float(value) <= 0:
            break
        total += 1
    return total


def _max_drawdown(future_close: pd.Series, base_close: float) -> float:
    values = [float(base_close), *future_close.astype(float).tolist()]
    peak = values[0]
    drawdowns = []
    for value in values[1:]:
        peak = max(peak, value)
        drawdowns.append(value / peak - 1)
    return float(min(drawdowns)) if drawdowns else 0.0


def _horizons_from_columns(frame: pd.DataFrame, prefix: str) -> list[int]:
    horizons = []
    for column in frame.columns:
        if column.startswith(prefix) and column.endswith("d"):
            raw = column.removeprefix(prefix).removesuffix("d")
            if raw.isdigit():
                horizons.append(int(raw))
    return sorted(set(horizons))


def _median(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    return float(numeric.median()) if len(numeric) else 0.0


def _win_rate(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    return float((numeric > 0).mean()) if len(numeric) else 0.0


def _summary(report: dict) -> str:
    days = report.get("median_remaining_positive_days", 0)
    win_rate = report.get("win_rate_5d", report.get("win_rate_3d", 0.0))
    return (
        f"历史相似样本 {report['sample_count']} 个：中位还能走 {days:.0f} 天，"
        f"后续胜率约 {win_rate:.0%}。这只是样本分布，不是买卖指令。"
    )


def _empty_report(state: str, trend_days: int) -> dict:
    return {
        "state": state,
        "trend_days": int(trend_days),
        "sample_count": 0,
        "median_remaining_positive_days": 0.0,
        "summary": "历史相似样本不足，暂时不能回答还能走多久。",
    }
