"""Candidate basket persistence and evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.compute import risk_engine
from src.compute.divergence import hedge_pairs, hedge_score
from src.compute.portfolio_exposure import match_sector_name

BASKET_PATH = Path("data/account/basket.json")


def load_basket() -> list[str]:
    if not BASKET_PATH.exists():
        return []
    data = json.loads(BASKET_PATH.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("items", [])
    return [str(item) for item in data]


def save_basket(items: list[str]) -> None:
    BASKET_PATH.parent.mkdir(parents=True, exist_ok=True)
    unique = list(dict.fromkeys(str(item) for item in items if str(item).strip()))
    BASKET_PATH.write_text(
        json.dumps(unique, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def evaluate_basket(
    items: list[str],
    panel: pd.DataFrame,
    corr: pd.DataFrame,
    account: dict,
) -> dict:
    available = panel["sector"].dropna().astype(str).tolist() if not panel.empty else []
    selected = list(
        dict.fromkeys(
            str(match_sector_name(str(item), available) or item)
            for item in items
            if str(item).strip()
        )
    )
    pairs = hedge_pairs(selected, corr, threshold=-0.3)
    score = hedge_score(selected, corr)
    buy_amount = float(account.get("basket_buy_amount") or account.get("buy_amount") or 0.0)
    total_assets = float(account.get("total_assets") or 0.0)
    debt = float(account.get("debt") or 0.0)
    guarantee_after = (
        risk_engine.guarantee_ratio_after_buy(total_assets, debt, buy_amount)
        if debt > 0
        else None
    )
    per_item = [_panel_item(sector, panel) for sector in selected]
    return {
        "hedge_score": score,
        "hedge_pairs": pairs,
        "guarantee_after": guarantee_after,
        "verdict": _verdict(score, pairs),
        "per_item": per_item,
    }


def _panel_item(sector: str, panel: pd.DataFrame) -> dict:
    matched = panel.loc[panel["sector"].astype(str) == sector] if not panel.empty else pd.DataFrame()
    if matched.empty:
        return {
            "sector": sector,
            "state": "未知",
            "trend_days": 0,
            "turning_point": False,
        }
    row = matched.iloc[0]
    return {
        "sector": sector,
        "state": str(row.get("state", "未知")),
        "trend_days": int(row.get("trend_days", 0) or 0),
        "turning_point": bool(row.get("turning_point", False)),
    }


def _verdict(score: float, pairs: list[list[str]]) -> str:
    if score >= 0.5:
        names = "、".join(f"{left}↔{right}" for left, right in pairs)
        return f"红色对冲警告：你在自我对冲，{names}"
    if score >= 0.3:
        return "黄色提醒：候选之间存在一定负相关，注意节奏分化。"
    return "绿色：候选方向相对一致，仍需看资金和拐点。"
