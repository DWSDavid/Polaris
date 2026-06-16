"""Walk-forward threshold calibration."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

import pandas as pd

from src.research.backtest import evaluate_signal


def walk_forward_splits(dates: Iterable, k: int = 3) -> list[tuple[list[int], list[int]]]:
    series = pd.Series(list(dates)).reset_index(drop=True)
    unique_dates = list(pd.Series(series.dropna().unique()).sort_values())
    if len(unique_dates) < 2:
        return []
    folds = max(1, min(int(k), len(unique_dates) - 1))
    test_size = max(1, len(unique_dates) // (folds + 1))
    splits = []
    for fold in range(folds):
        test_start = len(unique_dates) - test_size * (folds - fold)
        test_end = test_start + test_size
        if test_start <= 0:
            continue
        train_dates = set(unique_dates[:test_start])
        test_dates = set(unique_dates[test_start:test_end])
        train_idx = series[series.isin(train_dates)].index.tolist()
        test_idx = series[series.isin(test_dates)].index.tolist()
        if train_idx and test_idx:
            splits.append((train_idx, test_idx))
    return splits


def calibrate_threshold(
    df: pd.DataFrame,
    grid: Iterable[float],
    objective: str = "hit_rate_return",
    score_col: str = "score",
    return_col: str = "fwd_return",
    date_col: str = "week",
    k: int = 4,
) -> dict:
    if df.empty:
        empty = evaluate_signal(pd.DataFrame(), "signal", return_col)
        return {"best": None, "in_sample": empty, "out_sample": empty, "oos_beats_baseline": False, "folds": []}

    frame = df.sort_values(date_col).reset_index(drop=True).copy()
    splits = walk_forward_splits(frame[date_col], k=k)
    fold_rows = []
    train_evals = []
    test_evals = []
    selected_thresholds = []

    for train_idx, test_idx in splits:
        train = frame.iloc[train_idx].copy()
        test = frame.iloc[test_idx].copy()
        best_threshold, best_eval, best_score = _select_threshold(
            train, grid, objective, score_col, return_col
        )
        selected_thresholds.append(best_threshold)
        test_eval = _eval_threshold(test, best_threshold, score_col, return_col)
        train_evals.append(best_eval)
        test_evals.append(test_eval)
        fold_rows.append(
            {
                "threshold": best_threshold,
                "objective_score": best_score,
                "train": best_eval,
                "test": test_eval,
            }
        )

    best = _consensus_threshold(selected_thresholds)
    in_sample = _aggregate_metrics(train_evals)
    out_sample = _aggregate_metrics(test_evals)
    return {
        "best": best,
        "in_sample": in_sample,
        "out_sample": out_sample,
        "oos_beats_baseline": _beats_baseline(out_sample),
        "folds": fold_rows,
    }


def _select_threshold(
    frame: pd.DataFrame,
    grid: Iterable[float],
    objective: str,
    score_col: str,
    return_col: str,
) -> tuple[float, dict, float]:
    candidates = []
    for threshold in grid:
        metrics = _eval_threshold(frame, threshold, score_col, return_col)
        candidates.append((threshold, metrics, _objective_score(metrics, objective)))
    if not candidates:
        empty = evaluate_signal(pd.DataFrame(), "signal", return_col)
        return 0.0, empty, 0.0
    return max(candidates, key=lambda item: (item[2], float(item[0])))


def _eval_threshold(
    frame: pd.DataFrame,
    threshold: float,
    score_col: str,
    return_col: str,
) -> dict:
    payload = frame.copy()
    payload["signal"] = pd.to_numeric(payload[score_col], errors="coerce") >= float(threshold)
    return evaluate_signal(payload, "signal", return_col)


def _objective_score(metrics: dict, objective: str) -> float:
    if objective == "hit_rate":
        return float(metrics.get("hit_rate", 0.0))
    if objective == "avg_return":
        return float(metrics.get("avg_return", 0.0))
    return float(metrics.get("hit_rate", 0.0)) * max(float(metrics.get("avg_return", 0.0)), 0.0)


def _aggregate_metrics(items: list[dict]) -> dict:
    if not items:
        return evaluate_signal(pd.DataFrame(), "signal", "return")
    totals = {key: 0.0 for key in items[0] if key != "n"}
    total_n = sum(int(item.get("n", 0)) for item in items)
    baseline_n = sum(int(item.get("baseline_n", 0)) for item in items)
    out = {"n": total_n, "baseline_n": baseline_n}
    for key in ["hit_rate", "avg_return", "median_return", "max_drawdown"]:
        out[key] = _weighted_mean(items, key, "n")
    for key in ["baseline_hit_rate", "baseline_avg_return"]:
        out[key] = _weighted_mean(items, key, "baseline_n")
    return out


def _weighted_mean(items: list[dict], key: str, weight_key: str) -> float:
    total_weight = sum(int(item.get(weight_key, 0)) for item in items)
    if total_weight == 0:
        return 0.0
    return float(
        sum(float(item.get(key, 0.0)) * int(item.get(weight_key, 0)) for item in items)
        / total_weight
    )


def _consensus_threshold(thresholds: list[float]) -> float | None:
    if not thresholds:
        return None
    counts = Counter(thresholds)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _beats_baseline(metrics: dict) -> bool:
    return (
        float(metrics.get("hit_rate", 0.0)) > float(metrics.get("baseline_hit_rate", 0.0))
        and float(metrics.get("avg_return", 0.0))
        > float(metrics.get("baseline_avg_return", 0.0))
        and float(metrics.get("avg_return", 0.0)) > 0
    )
