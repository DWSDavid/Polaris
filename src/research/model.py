"""Explainable direction model with time-series validation."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

MODEL_CACHE_DIR = Path("data/cache/model")


def train_model(
    dataset: pd.DataFrame,
    feature_cols: list[str] | None = None,
    label_col: str = "label",
    n_splits: int = 5,
) -> dict:
    if dataset.empty:
        raise ValueError("dataset is empty")
    feature_cols = feature_cols or _default_feature_cols(dataset, label_col)
    frame = dataset.sort_values(_sort_columns(dataset)).reset_index(drop=True).copy()
    x = frame[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y = pd.to_numeric(frame[label_col], errors="coerce").fillna(0).astype(int)
    if y.nunique() < 2:
        raise ValueError("label must contain both classes")

    model = _new_model()
    oos_pred = pd.Series(np.nan, index=frame.index, dtype=float)
    split_count = max(2, min(int(n_splits), len(frame) - 1))
    for train_idx, test_idx in TimeSeriesSplit(n_splits=split_count).split(x):
        y_train = y.iloc[train_idx]
        if y_train.nunique() < 2:
            continue
        fold_model = _new_model()
        fold_model.fit(x.iloc[train_idx], y_train)
        oos_pred.iloc[test_idx] = fold_model.predict_proba(x.iloc[test_idx])[:, 1]

    model.fit(x, y)
    in_pred = model.predict_proba(x)[:, 1]
    valid = oos_pred.notna()
    result = {
        "model": model,
        "feature_importance": _feature_importance(model, feature_cols),
        "in_sample_auc": _safe_auc(y, in_pred),
        "out_sample_auc": _safe_auc(y[valid], oos_pred[valid]),
        "baseline_auc": _baseline_auc(frame, y, feature_cols),
    }
    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_CACHE_DIR / "direction_model.joblib")
    return result


def predict_proba(model, row: dict | pd.Series | pd.DataFrame) -> float:
    if isinstance(row, pd.DataFrame):
        frame = row.copy()
    else:
        frame = pd.DataFrame([dict(row)])
    probability = model.predict_proba(frame)[:, 1][0]
    return float(max(0.0, min(1.0, probability)))


def derive_direction_weights(feature_importance: dict[str, float]) -> dict[str, float]:
    total = sum(abs(float(value)) for value in feature_importance.values())
    if total <= 0:
        return {key: 0.0 for key in feature_importance}
    return {key: abs(float(value)) / total for key, value in feature_importance.items()}


def _new_model() -> Pipeline:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            ("logit", LogisticRegression(max_iter=1000, random_state=42)),
        ]
    )


def _feature_importance(model: Pipeline, feature_cols: list[str]) -> dict[str, float]:
    coefficients = model.named_steps["logit"].coef_[0]
    values = np.abs(coefficients)
    total = values.sum()
    if total <= 0:
        return {name: 0.0 for name in feature_cols}
    return {name: float(value / total) for name, value in zip(feature_cols, values)}


def _safe_auc(y_true, scores) -> float:
    y_series = pd.Series(y_true).dropna()
    score_series = pd.Series(scores).dropna()
    common = min(len(y_series), len(score_series))
    if common == 0:
        return 0.5
    y_series = y_series.iloc[:common]
    score_series = score_series.iloc[:common]
    if y_series.nunique() < 2:
        return 0.5
    return float(roc_auc_score(y_series, score_series))


def _baseline_auc(frame: pd.DataFrame, y: pd.Series, feature_cols: list[str]) -> float:
    preferred = [col for col in ["cum_inflow_20d", "flow_strength", "trend_days", "midterm_trend"] if col in feature_cols]
    if not preferred:
        preferred = feature_cols[: min(2, len(feature_cols))]
    scores = frame[preferred].apply(pd.to_numeric, errors="coerce").fillna(0.0).sum(axis=1)
    return _safe_auc(y, scores)


def _default_feature_cols(dataset: pd.DataFrame, label_col: str) -> list[str]:
    excluded = {label_col, "sector", "week", "date", "trade_date"}
    return [
        column
        for column in dataset.columns
        if column not in excluded and pd.api.types.is_numeric_dtype(dataset[column])
    ]


def _sort_columns(dataset: pd.DataFrame) -> list[str]:
    if "week" in dataset.columns:
        return ["week", "sector"] if "sector" in dataset.columns else ["week"]
    if "date" in dataset.columns:
        return ["date", "sector"] if "sector" in dataset.columns else ["date"]
    return list(dataset.columns[:1])
