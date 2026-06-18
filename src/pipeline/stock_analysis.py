"""Assemble single-stock analysis payloads from market, sector, and context data."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from src.compute.stock_decision import build_stock_facts, evaluate_stock_setup
from src.data import akshare_client, em_client, em_context
from src.pipeline.sector_panel_v2 import build_sector_panel_v2


def build_stock_analysis_payload(
    query: str = "601688",
    sector_hint: str = "证券",
    holding: dict | None = None,
    days: int = 180,
    include_context: bool = False,
    include_history: bool = False,
) -> dict:
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    sector_name = sector_hint
    constituents = _safe_frame(em_client.industry_cons, sector_name)
    if constituents.empty:
        realtime_for_match = _safe_frame(em_client.industry_realtime)
        sector_name = _match_sector_name(realtime_for_match, sector_hint)
        if sector_name != sector_hint:
            constituents = _safe_frame(em_client.industry_cons, sector_name)
    stock = find_stock_snapshot(constituents, query)
    if not stock:
        market = _safe_frame(em_client.market_spot)
        stock = find_stock_snapshot(market, query)
    if not stock:
        symbol = to_symbol(query)
        code = symbol[2:]
        stock = {"code": code, "symbol": symbol, "name": query, "latest_price": 0.0}
    code = str(stock.get("code") or to_symbol(query)[2:]).zfill(6)
    symbol = str(stock.get("symbol") or to_symbol(code))
    stock["symbol"] = symbol
    stock["code"] = code

    daily = _safe_frame(akshare_client.daily_hist, symbol, start, end) if include_history else pd.DataFrame()
    flow = _safe_frame(akshare_client.individual_fund_flow, symbol) if include_history else pd.DataFrame()
    sector_panel = _sector_panel(
        sector_name,
        start,
        end,
        include_history=include_history,
    )
    sector_row = (
        sector_panel.iloc[0].to_dict()
        if not sector_panel.empty
        else {"sector": sector_hint, "state": "未知"}
    )
    facts = build_stock_facts(
        stock=stock,
        daily=daily,
        flow=flow,
        sector=sector_row,
        holding=holding,
    )
    context = _stock_context(symbol) if include_context else {}
    facts.update(_context_facts(context, facts.get("name", "")))
    decision = evaluate_stock_setup(facts)
    facts["decision"] = decision
    return {
        "facts": facts,
        "decision": decision,
        "stock": pd.DataFrame([stock]),
        "daily": daily,
        "flow": flow,
        "sector_panel": sector_panel,
        "context": context,
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def to_symbol(value: str) -> str:
    text = str(value or "").strip().upper()
    if text.startswith(("SH", "SZ")) and len(text) >= 8:
        return text[:2] + text[2:8].zfill(6)
    code = "".join(ch for ch in text if ch.isdigit())[:6].zfill(6)
    return f"SH{code}" if code.startswith(("5", "6", "9")) else f"SZ{code}"


def find_stock_snapshot(market: pd.DataFrame, query: str) -> dict:
    if market.empty:
        return {}
    text = str(query or "").strip()
    code = "".join(ch for ch in text if ch.isdigit())[:6]
    frame = market.copy()
    frame["code"] = frame.get("code", pd.Series("", index=frame.index)).astype(str).str.zfill(6)
    if code:
        matched = frame[frame["code"] == code.zfill(6)]
    else:
        names = frame.get("name", pd.Series("", index=frame.index)).fillna("").astype(str)
        matched = frame[names.str.contains(text, na=False)]
    if matched.empty:
        return {}
    return matched.iloc[0].to_dict()


def _match_sector_name(realtime: pd.DataFrame, sector_hint: str) -> str:
    if realtime.empty or "sector" not in realtime.columns:
        return sector_hint
    sectors = realtime["sector"].dropna().astype(str).tolist()
    if sector_hint in sectors:
        return sector_hint
    normalized_hint = _strip_suffix(sector_hint)
    for sector in sectors:
        if _strip_suffix(sector) == normalized_hint:
            return sector
    for sector in sectors:
        if normalized_hint and normalized_hint in _strip_suffix(sector):
            return sector
    return sector_hint


def _sector_panel(
    sector: str,
    start: str,
    end: str,
    include_history: bool = False,
) -> pd.DataFrame:
    realtime = _safe_frame(em_client.industry_realtime)
    flow_5d = _safe_frame(em_client.industry_fund_flow, "5日")
    flow_10d = _safe_frame(em_client.industry_fund_flow, "10日")
    hist = _safe_frame(em_client.industry_hist, sector, start, end) if include_history else pd.DataFrame()
    return build_sector_panel_v2(
        industry_realtime=realtime[realtime["sector"] == sector] if not realtime.empty else realtime,
        flow_5d=flow_5d[flow_5d["sector"] == sector] if not flow_5d.empty else flow_5d,
        flow_10d=flow_10d[flow_10d["sector"] == sector] if not flow_10d.empty else flow_10d,
        histories={sector: hist},
    )


def _stock_context(symbol: str) -> dict:
    code = symbol[2:]
    return {
        "dragon_tiger": _safe_frame(em_context.dragon_tiger),
        "research": _safe_frame(em_context.research_reports, code),
        "news": _safe_frame(em_context.stock_news, code),
    }


def _context_facts(context: dict, name: str) -> dict:
    dragon = context.get("dragon_tiger", pd.DataFrame())
    research = context.get("research", pd.DataFrame())
    news = context.get("news", pd.DataFrame())
    return {
        "dragon_tiger_active": _contains_name(dragon, name),
        "research_titles": _head_values(research, "title", 3),
        "news_titles": _head_values(news, "title", 3),
    }


def _contains_name(frame: pd.DataFrame, name: str) -> bool:
    if frame.empty or not name:
        return False
    names = frame.get("name", pd.Series(dtype=str)).dropna().astype(str)
    return bool(names.str.contains(str(name), regex=False).any())


def _head_values(frame: pd.DataFrame, column: str, limit: int) -> list[str]:
    if frame.empty or column not in frame.columns:
        return []
    return frame[column].dropna().astype(str).head(limit).tolist()


def _safe_frame(func, *args) -> pd.DataFrame:
    try:
        return func(*args)
    except Exception:
        return pd.DataFrame()


def _strip_suffix(value: str) -> str:
    text = str(value or "")
    for suffix in ("Ⅰ", "Ⅱ", "Ⅲ", "IV", "II", "III"):
        text = text.replace(suffix, "")
    return text.strip()
