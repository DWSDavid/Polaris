"""Tushare Pro client wrappers with parquet caching."""

import os

import tushare as ts
from dotenv import load_dotenv

from src.data import cache

load_dotenv(dotenv_path=".env")
_pro = None


def _pro_api():
    global _pro
    if _pro is None:
        _pro = ts.pro_api(os.environ["TUSHARE_TOKEN"])
    return _pro


def to_ts_code(symbol: str) -> str:
    return f"{symbol[2:]}.{symbol[:2].upper()}"


def _raw_daily(ts_code: str, start: str, end: str):
    return _pro_api().daily(ts_code=ts_code, start_date=start, end_date=end)


def daily(symbol: str, start: str, end: str):
    key = f"{symbol}_{start}_{end}"
    hit = cache.read("tushare", "daily", key)
    if hit is not None:
        return hit
    df = _raw_daily(to_ts_code(symbol), start, end)
    cache.write("tushare", "daily", key, df)
    return df


def _raw_daily_basic(ts_code: str, start: str, end: str):
    return _pro_api().daily_basic(ts_code=ts_code, start_date=start, end_date=end)


def daily_basic(symbol: str, start: str, end: str):
    key = f"{symbol}_{start}_{end}"
    hit = cache.read("tushare", "daily_basic", key)
    if hit is not None:
        return hit
    df = _raw_daily_basic(to_ts_code(symbol), start, end)
    cache.write("tushare", "daily_basic", key, df)
    return df
