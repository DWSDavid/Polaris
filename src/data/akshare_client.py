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


def _call_with_retry(fn, *args, attempts: int = 2):
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
