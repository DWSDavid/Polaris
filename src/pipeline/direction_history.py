"""Persist daily investment direction snapshots for continuity."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.data import cache
from src.data.sector_groups import filter_actionable_groups

HISTORY_DIR = cache.CACHE_DIR / "direction_history"


def build_direction_snapshot(
    ranked: list[dict],
    as_of: str | None = None,
    limit: int = 6,
) -> dict:
    timestamp = as_of or datetime.now().strftime("%Y-%m-%d %H:%M")
    frame = pd.DataFrame(ranked)
    if frame.empty:
        top: list[dict] = []
    else:
        top = (
            filter_actionable_groups(frame)
            .head(limit)
            .apply(lambda row: _snapshot_item(row.to_dict()), axis=1)
            .tolist()
        )
    names = "、".join(item["sector"] for item in top[:3]) or "暂无"
    return {
        "date": timestamp[:10],
        "as_of": timestamp,
        "top_directions": top,
        "summary": f"当日可观察方向：{names}。仅作记录，不代表自动买卖。",
    }


def save_direction_snapshot(snapshot: dict, history_dir: Path | None = None) -> Path:
    target_dir = history_dir or HISTORY_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    date = str(snapshot.get("date") or datetime.now().strftime("%Y-%m-%d"))
    path = target_dir / f"{date}.json"
    path.write_text(json.dumps(_jsonable(snapshot), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_direction_history(limit: int = 20, history_dir: Path | None = None) -> list[dict]:
    target_dir = history_dir or HISTORY_DIR
    if not target_dir.exists():
        return []
    rows: list[dict] = []
    for path in sorted(target_dir.glob("*.json"), reverse=True):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
        if len(rows) >= limit:
            break
    return rows


def _snapshot_item(item: dict) -> dict:
    return {
        "sector": str(item.get("sector", "")),
        "score": round(_num(item.get("score")), 2),
        "state": str(item.get("state", "未知")),
        "trend_days": int(round(_num(item.get("trend_days")))),
        "cum_inflow_20d": _num(item.get("cum_inflow_20d")),
        "position_in_box": round(_num(item.get("position_in_box")), 2),
        "top_leaders": str(item.get("top_leaders", "")),
        "children": _list_text(item.get("children")),
        "reasons": [str(reason) for reason in (item.get("reasons") or [])[:4]],
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            return str(value)
    return value


def _num(value, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _list_text(value) -> str:
    if isinstance(value, (list, tuple, set)):
        return "、".join(str(item) for item in list(value)[:8])
    return str(value or "")
