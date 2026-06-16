"""Eastmoney context data via AKShare public interfaces."""

from __future__ import annotations

from datetime import date, datetime, timezone

import akshare as ak
import pandas as pd

from src.data import cache

CACHE_SOURCE = "em_context"
CACHE_TS_COL = "__cached_at"
TTL_SECONDS = 24 * 60 * 60


def northbound_flow(force: bool = False) -> pd.DataFrame:
    key = date.today().isoformat()
    cached = None if force else _read_ttl("northbound_flow", key)
    if cached is not None:
        return cached
    out = _normalize_northbound_flow(_raw_northbound_flow())
    _write_ttl("northbound_flow", key, out)
    return out


def dragon_tiger(day: str | None = None, force: bool = False) -> pd.DataFrame:
    query_day = day or date.today().strftime("%Y%m%d")
    cached = None if force else _read_ttl("dragon_tiger", query_day)
    if cached is not None:
        return cached
    out = _normalize_dragon_tiger(_raw_dragon_tiger(query_day))
    _write_ttl("dragon_tiger", query_day, out)
    return out


def research_reports(symbol: str, force: bool = False) -> pd.DataFrame:
    key = _safe_key(symbol)
    cached = None if force else _read_ttl("research_reports", key)
    if cached is not None:
        return cached
    out = _normalize_research_reports(_raw_research_reports(symbol))
    _write_ttl("research_reports", key, out)
    return out


def stock_news(symbol: str, force: bool = False) -> pd.DataFrame:
    key = _safe_key(symbol)
    cached = None if force else _read_ttl("stock_news", key)
    if cached is not None:
        return cached
    out = _normalize_stock_news(_raw_stock_news(symbol))
    _write_ttl("stock_news", key, out)
    return out


def _raw_northbound_flow() -> pd.DataFrame:
    return ak.stock_hsgt_fund_flow_summary_em()


def _raw_dragon_tiger(day: str) -> pd.DataFrame:
    return ak.stock_lhb_detail_em(start_date=day, end_date=day)


def _raw_research_reports(symbol: str) -> pd.DataFrame:
    return ak.stock_research_report_em(symbol=symbol)


def _raw_stock_news(symbol: str) -> pd.DataFrame:
    previous = None
    has_option = hasattr(pd.options, "future") and hasattr(pd.options.future, "infer_string")
    if has_option:
        previous = pd.options.future.infer_string
        pd.options.future.infer_string = False
    try:
        return ak.stock_news_em(symbol=symbol)
    finally:
        if has_option:
            pd.options.future.infer_string = previous


def _normalize_northbound_flow(raw: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=raw.index)
    out["trade_date"] = _text(raw, "交易日")
    out["connect_type"] = _text(raw, "类型")
    out["board"] = _text(raw, "板块")
    out["direction"] = _text(raw, "资金方向")
    out["trade_status"] = _text(raw, "交易状态")
    out["net_buy_amount"] = _num(raw, "成交净买额")
    out["fund_net_inflow"] = _num(raw, "资金净流入")
    out["daily_balance"] = _num(raw, "当日资金余额")
    out["up_count"] = _num(raw, "上涨数")
    out["flat_count"] = _num(raw, "持平数")
    out["down_count"] = _num(raw, "下跌数")
    out["index_name"] = _text(raw, "相关指数")
    out["index_pct_chg"] = _num(raw, "指数涨跌幅")
    out["data_source"] = "akshare-eastmoney"
    return out.reset_index(drop=True)


def _normalize_dragon_tiger(raw: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=raw.index)
    out["trade_date"] = _text(raw, "上榜日")
    out["code"] = _text(raw, "代码").str.zfill(6)
    out["name"] = _text(raw, "名称")
    out["interpretation"] = _text(raw, "解读")
    out["close"] = _num(raw, "收盘价")
    out["pct_chg"] = _num(raw, "涨跌幅")
    out["net_buy"] = _num(raw, "龙虎榜净买额")
    out["buy_amount"] = _num(raw, "龙虎榜买入额")
    out["sell_amount"] = _num(raw, "龙虎榜卖出额")
    out["list_amount"] = _num(raw, "龙虎榜成交额")
    out["market_amount"] = _num(raw, "市场总成交额")
    out["net_buy_ratio"] = _num(raw, "净买额占总成交比")
    out["list_amount_ratio"] = _num(raw, "成交额占总成交比")
    out["turnover"] = _num(raw, "换手率")
    out["circ_mv"] = _num(raw, "流通市值")
    out["reason"] = _text(raw, "上榜原因")
    out["after_1d"] = _num(raw, "上榜后1日")
    out["after_2d"] = _num(raw, "上榜后2日")
    out["after_5d"] = _num(raw, "上榜后5日")
    out["after_10d"] = _num(raw, "上榜后10日")
    out["data_source"] = "akshare-eastmoney"
    return out.reset_index(drop=True)


def _normalize_research_reports(raw: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=raw.index)
    out["symbol"] = _text(raw, "股票代码").str.zfill(6)
    out["name"] = _text(raw, "股票简称")
    out["title"] = _text(raw, "报告名称")
    out["rating"] = _text(raw, "东财评级")
    out["org"] = _text(raw, "机构")
    out["report_count_1m"] = _num(raw, "近一月个股研报数")
    out["industry"] = _text(raw, "行业")
    out["date"] = _text(raw, "日期")
    out["pdf_url"] = _text(raw, "报告PDF链接")
    out["data_source"] = "akshare-eastmoney"
    return out.reset_index(drop=True)


def _normalize_stock_news(raw: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=raw.index)
    out["symbol"] = _text(raw, "关键词").str.zfill(6)
    out["title"] = _text(raw, "新闻标题")
    out["content"] = _text(raw, "新闻内容")
    out["publish_time"] = _text(raw, "发布时间")
    out["source"] = _text(raw, "文章来源")
    out["url"] = _text(raw, "新闻链接")
    out["data_source"] = "akshare-eastmoney"
    return out.reset_index(drop=True)


def _read_ttl(dataset: str, key: str) -> pd.DataFrame | None:
    hit = cache.read(CACHE_SOURCE, dataset, key)
    if hit is None or hit.empty or CACHE_TS_COL not in hit.columns:
        return None
    cached_at = pd.to_datetime(hit[CACHE_TS_COL].iloc[0], utc=True, errors="coerce")
    if pd.isna(cached_at):
        return None
    age = (datetime.now(timezone.utc) - cached_at.to_pydatetime()).total_seconds()
    if age > TTL_SECONDS:
        return None
    return hit.drop(columns=[CACHE_TS_COL])


def _write_ttl(dataset: str, key: str, df: pd.DataFrame) -> None:
    payload = df.copy()
    payload[CACHE_TS_COL] = datetime.now(timezone.utc).isoformat()
    cache.write(CACHE_SOURCE, dataset, key, payload)


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(pd.NA, index=frame.index, dtype="Float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _text(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype="string")
    return frame[column].fillna("").astype(str)


def _safe_key(value: str) -> str:
    return str(value).replace("/", "_").replace("\\", "_").replace(":", "_") or "unknown"
