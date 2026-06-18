"""Hot-rank and Dragon Tiger focus pool."""

from __future__ import annotations

import pandas as pd

from src.compute.trend import consecutive_up_days, trend_sign


def build_hot_dragon_focus(
    hot_rank: pd.DataFrame,
    dragon_tiger: pd.DataFrame,
    top_n: int = 100,
    histories: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    if hot_rank.empty:
        return _empty_focus()

    hot = hot_rank.copy()
    hot["code"] = _normalize_code(hot.get("code", pd.Series(index=hot.index)))
    hot["hot_rank"] = pd.to_numeric(hot.get("hot_rank"), errors="coerce")
    hot = hot.loc[hot["hot_rank"].notna() & (hot["hot_rank"] <= top_n)].copy()
    hot = _filter_noise(hot)
    if hot.empty:
        return _empty_focus()

    dragon = _group_dragon_tiger(dragon_tiger)
    out = hot.merge(dragon, on="code", how="left")
    out["dragon_tiger_count"] = out["dragon_tiger_count"].fillna(0).astype(int)
    out["dragon_tiger_net_buy"] = (
        pd.to_numeric(out["dragon_tiger_net_buy"], errors="coerce").fillna(0.0)
    )
    out["dragon_tiger_reasons"] = out["dragon_tiger_reasons"].fillna("")
    out["dragon_tiger_latest_date"] = out["dragon_tiger_latest_date"].fillna("")
    out["dragon_tiger_on_list"] = (
        out["dragon_tiger_count"].map(lambda value: bool(value > 0)).astype(object)
    )
    out = _attach_history_metrics(out, histories or {})

    hot_component = ((top_n + 1 - out["hot_rank"]).clip(lower=0) / top_n).fillna(0)
    lhb_component = out["dragon_tiger_on_list"].map(lambda value: 1.0 if value else 0.0)
    positive_net = out["dragon_tiger_net_buy"].clip(lower=0)
    max_net = float(positive_net.max() or 0)
    net_component = positive_net / max_net if max_net > 0 else positive_net
    out["focus_score"] = (
        60 * hot_component + 25 * lhb_component + 15 * net_component
    ).round(2)
    out["focus_reason"] = out.apply(_focus_reason, axis=1)

    columns = [
        "hot_rank",
        "focus_score",
        "code",
        "market_code",
        "name",
        "latest_price",
        "pct_chg",
        "consecutive_up_days",
        "trend_days",
        "midterm_trend",
        "return_20d",
        "dragon_tiger_on_list",
        "dragon_tiger_count",
        "dragon_tiger_net_buy",
        "dragon_tiger_latest_date",
        "dragon_tiger_reasons",
        "focus_reason",
    ]
    for column in columns:
        if column not in out.columns:
            out[column] = pd.NA
    return out[columns].sort_values(
        ["focus_score", "hot_rank"], ascending=[False, True]
    ).reset_index(drop=True)


def _group_dragon_tiger(dragon_tiger: pd.DataFrame) -> pd.DataFrame:
    if dragon_tiger.empty or "code" not in dragon_tiger.columns:
        return pd.DataFrame(
            columns=[
                "code",
                "dragon_tiger_count",
                "dragon_tiger_net_buy",
                "dragon_tiger_latest_date",
                "dragon_tiger_reasons",
            ]
        )
    dragon = dragon_tiger.copy()
    dragon["code"] = _normalize_code(dragon["code"])
    dragon["net_buy"] = pd.to_numeric(dragon.get("net_buy"), errors="coerce").fillna(0)
    if "reason" not in dragon.columns:
        dragon["reason"] = ""
    if "trade_date" not in dragon.columns:
        dragon["trade_date"] = ""
    grouped = (
        dragon.groupby("code", as_index=False)
        .agg(
            dragon_tiger_count=("code", "size"),
            dragon_tiger_net_buy=("net_buy", "sum"),
            dragon_tiger_latest_date=("trade_date", "max"),
            dragon_tiger_reasons=("reason", _join_reasons),
        )
    )
    return grouped


def _attach_history_metrics(
    focus: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    out = focus.copy()
    metrics = []
    normalized = {_normalize_single_code(code): frame for code, frame in histories.items()}
    for code in out["code"].astype(str):
        history = normalized.get(_normalize_single_code(code), pd.DataFrame())
        metrics.append(_history_metrics(history))
    metric_frame = pd.DataFrame(metrics, index=out.index)
    for column in ["consecutive_up_days", "trend_days", "midterm_trend", "return_20d"]:
        out[column] = metric_frame[column]
    return out


def _history_metrics(history: pd.DataFrame) -> dict:
    if history is None or history.empty:
        return _empty_history_metrics()
    pct = _pct_series(history)
    close = _close_series(history)
    return {
        "consecutive_up_days": int(consecutive_up_days(pct)),
        "trend_days": int(_signed_streak_days(pct)),
        "midterm_trend": int(trend_sign(close, window=20)),
        "return_20d": round(_return_pct(close, window=20), 3),
    }


def _pct_series(history: pd.DataFrame) -> pd.Series:
    for column in ("pct", "pct_chg", "涨跌幅"):
        if column in history.columns:
            return pd.to_numeric(history[column], errors="coerce").dropna()
    close = _close_series(history)
    return close.pct_change().fillna(0) * 100


def _close_series(history: pd.DataFrame) -> pd.Series:
    if "close" not in history.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(history["close"], errors="coerce").dropna()


def _signed_streak_days(pct: pd.Series) -> int:
    clean = pd.to_numeric(pct, errors="coerce").dropna()
    if clean.empty or clean.iloc[-1] == 0:
        return 0
    sign = 1 if clean.iloc[-1] > 0 else -1
    count = 0
    for value in reversed(clean.tolist()):
        if value == 0:
            break
        if (value > 0 and sign > 0) or (value < 0 and sign < 0):
            count += 1
        else:
            break
    return sign * count


def _return_pct(close: pd.Series, window: int) -> float:
    clean = pd.to_numeric(close, errors="coerce").dropna()
    if len(clean) < window + 1:
        return 0.0
    base = float(clean.iloc[-(window + 1)])
    if base == 0:
        return 0.0
    return (float(clean.iloc[-1]) / base - 1) * 100


def _empty_history_metrics() -> dict:
    return {
        "consecutive_up_days": 0,
        "trend_days": 0,
        "midterm_trend": 0,
        "return_20d": 0.0,
    }


def _filter_noise(frame: pd.DataFrame) -> pd.DataFrame:
    if "name" not in frame.columns:
        return frame
    names = frame["name"].fillna("").astype(str)
    return frame.loc[~names.str.contains("ST", case=False, regex=False)].copy()


def _focus_reason(row: pd.Series) -> str:
    rank = int(row.get("hot_rank") or 0)
    if bool(row.get("dragon_tiger_on_list")):
        net_buy = float(row.get("dragon_tiger_net_buy") or 0)
        if net_buy > 0:
            return f"热度前{rank}+龙虎榜净买，重点观察资金接力"
        if net_buy < 0:
            return f"热度前{rank}+龙虎榜净卖，重点观察分歧消化"
        return f"热度前{rank}+龙虎榜上榜，重点观察席位分歧"
    return f"热度前{rank}，先观察是否有资金行为确认"


def _join_reasons(values: pd.Series) -> str:
    unique = []
    for value in values.dropna().astype(str):
        if value and value not in unique:
            unique.append(value)
    return "；".join(unique[:3])


def _normalize_code(values: pd.Series) -> pd.Series:
    text = values.fillna("").astype(str)
    text = text.str.replace(r"^[A-Z]+", "", regex=True)
    return text.str.zfill(6)


def _normalize_single_code(value: str) -> str:
    text = str(value or "")
    text = pd.Series([text]).str.replace(r"^[A-Z]+", "", regex=True).str.zfill(6)
    return str(text.iloc[0])


def _empty_focus() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "hot_rank",
            "focus_score",
            "code",
            "market_code",
            "name",
            "latest_price",
            "pct_chg",
            "consecutive_up_days",
            "trend_days",
            "midterm_trend",
            "return_20d",
            "dragon_tiger_on_list",
            "dragon_tiger_count",
            "dragon_tiger_net_buy",
            "dragon_tiger_latest_date",
            "dragon_tiger_reasons",
            "focus_reason",
        ]
    )
