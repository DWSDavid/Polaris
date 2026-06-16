"""AKShare client wrappers with parquet caching."""

import akshare as ak
import pandas as pd

from src.data import cache

_DAILY_COLS = {
    "日期": "date",
    "收盘": "close",
    "成交额": "amount",
    "涨跌幅": "pct",
}


def _call_with_retry(fn, *args, attempts: int = 3):
    last_error = None
    for _ in range(attempts):
        try:
            return fn(*args)
        except Exception as exc:  # AKShare may surface requests errors inconsistently.
            last_error = exc
    raise last_error


def _raw_daily_hist(code6: str, start: str, end: str) -> pd.DataFrame:
    return ak.stock_zh_a_hist(
        symbol=code6,
        period="daily",
        start_date=start,
        end_date=end,
        adjust="qfq",
    )


def _norm_daily(df: pd.DataFrame) -> pd.DataFrame:
    renamed = df.rename(columns=_DAILY_COLS)
    cols = [col for col in ["date", "close", "amount", "pct"] if col in renamed.columns]
    return renamed[cols]


def _symbol_from_code(code: str) -> str:
    code = str(code).zfill(6)
    return f"SH{code}" if code.startswith(("5", "6", "9")) else f"SZ{code}"


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(pd.NA, index=frame.index, dtype="Float64")
    return pd.to_numeric(frame[column], errors="coerce")


def normalize_realtime_stock_spot(raw: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=raw.index)
    out["code"] = raw["代码"].astype(str).str.zfill(6)
    out["symbol"] = out["code"].map(_symbol_from_code)
    out["name"] = raw["名称"].astype(str)
    out["latest_price"] = _num(raw, "最新价")
    out["pct_chg"] = _num(raw, "涨跌幅")
    out["amount"] = _num(raw, "成交额")
    out["volume_ratio"] = _num(raw, "量比")
    out["turnover_rate"] = _num(raw, "换手率")
    out["pe_ttm"] = _num(raw, "市盈率-动态")
    out["pb"] = _num(raw, "市净率")
    out["total_mv"] = _num(raw, "总市值")
    out["circ_mv"] = _num(raw, "流通市值")
    out["speed"] = _num(raw, "涨速")
    out["five_min_pct_chg"] = _num(raw, "5分钟涨跌")
    out["data_quality"] = "realtime_snapshot"
    return out.reset_index(drop=True)


def normalize_industry_spot(raw: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=raw.index)
    out["industry"] = raw["板块名称"].astype(str)
    out["industry_code"] = raw["板块代码"].astype(str)
    out["pct_chg"] = _num(raw, "涨跌幅")
    out["total_mv"] = _num(raw, "总市值")
    out["turnover_rate"] = _num(raw, "换手率")
    out["up_count"] = _num(raw, "上涨家数")
    out["down_count"] = _num(raw, "下跌家数")
    out["leading_stock"] = raw.get("领涨股票", pd.Series("-", index=raw.index)).astype(
        str
    )
    out["leading_stock_pct_chg"] = _num(raw, "领涨股票-涨跌幅")
    out["data_quality"] = "realtime_snapshot"
    return out.reset_index(drop=True)


def normalize_sector_fund_flow(raw: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=raw.index)
    out["industry"] = raw["名称"].astype(str)
    out["today_pct_chg"] = _num(raw, "今日涨跌幅")
    out["today_main_net_inflow"] = _num(raw, "今日主力净流入-净额")
    out["today_main_net_inflow_pct"] = _num(raw, "今日主力净流入-净占比")
    if "今日主力净流入最大股" in raw.columns:
        out["main_inflow_leader"] = raw["今日主力净流入最大股"].astype(str)
    return out.reset_index(drop=True)


def realtime_stock_spot() -> pd.DataFrame:
    raw = _call_with_retry(ak.stock_zh_a_spot_em)
    return normalize_realtime_stock_spot(raw)


def realtime_industry_spot() -> pd.DataFrame:
    raw = _call_with_retry(ak.stock_board_industry_name_em)
    return normalize_industry_spot(raw)


def realtime_industry_fund_flow() -> pd.DataFrame:
    raw = _call_with_retry(
        ak.stock_sector_fund_flow_rank,
        "今日",
        "行业资金流",
    )
    return normalize_sector_fund_flow(raw)


def daily_hist(symbol: str, start: str, end: str) -> pd.DataFrame:
    key = f"{symbol}_{start}_{end}"
    hit = cache.read("akshare", "daily", key)
    if hit is not None:
        return hit
    df = _norm_daily(_call_with_retry(_raw_daily_hist, symbol[2:], start, end))
    cache.write("akshare", "daily", key, df)
    return df


def _raw_individual_fund_flow(code6: str, market: str) -> pd.DataFrame:
    return ak.stock_individual_fund_flow(stock=code6, market=market)


def individual_fund_flow(symbol: str) -> pd.DataFrame:
    key = symbol
    hit = cache.read("akshare", "individual_flow", key)
    if hit is not None:
        return hit
    df = _raw_individual_fund_flow(symbol[2:], symbol[:2].lower())
    cache.write("akshare", "individual_flow", key, df)
    return df


def _raw_sector_fund_flow() -> pd.DataFrame:
    return ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")


def sector_fund_flow() -> pd.DataFrame:
    hit = cache.read("akshare", "sector_flow", "today")
    if hit is not None:
        return hit
    df = _raw_sector_fund_flow()
    cache.write("akshare", "sector_flow", "today", df)
    return df
