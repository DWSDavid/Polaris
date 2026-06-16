"""Eastmoney industry and market clients for Polaris v2."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd
import requests

from src.data import cache

TTL_SECONDS = 600
CACHE_SOURCE = "em"
CACHE_TS_COL = "__cached_at"

CLIST_URL = "https://push2delay.eastmoney.com/api/qt/clist/get"
KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}

INDUSTRY_REALTIME_COLS = {
    "f12": "板块代码",
    "f14": "板块名称",
    "f3": "涨跌幅",
    "f6": "成交额",
    "f20": "总市值",
    "f8": "换手率",
    "f104": "上涨家数",
    "f105": "下跌家数",
    "f128": "领涨股票",
    "f136": "领涨股票-涨跌幅",
    "f62": "主力净流入-净额",
}
MARKET_SPOT_COLS = {
    "f12": "代码",
    "f14": "名称",
    "f2": "最新价",
    "f3": "涨跌幅",
    "f4": "涨跌额",
    "f5": "成交量",
    "f6": "成交额",
    "f7": "振幅",
    "f8": "换手率",
    "f9": "市盈率-动态",
    "f10": "量比",
    "f20": "总市值",
    "f21": "流通市值",
    "f23": "市净率",
}
CONS_COLS = {
    "f12": "代码",
    "f14": "名称",
    "f2": "最新价",
    "f3": "涨跌幅",
    "f4": "涨跌额",
    "f5": "成交量",
    "f6": "成交额",
    "f7": "振幅",
    "f8": "换手率",
    "f9": "市盈率-动态",
    "f20": "总市值",
    "f21": "流通市值",
    "f23": "市净率",
}
FUND_FLOW_SPECS = {
    "今日": {
        "fid": "f62",
        "stat": "1",
        "fields": {
            "f14": "名称",
            "f3": "今日涨跌幅",
            "f62": "今日主力净流入-净额",
            "f184": "今日主力净流入-净占比",
            "f204": "今日主力净流入最大股",
        },
    },
    "5日": {
        "fid": "f164",
        "stat": "5",
        "fields": {
            "f14": "名称",
            "f109": "5日涨跌幅",
            "f164": "5日主力净流入-净额",
            "f165": "5日主力净流入-净占比",
            "f257": "5日主力净流入最大股",
        },
    },
    "10日": {
        "fid": "f174",
        "stat": "10",
        "fields": {
            "f14": "名称",
            "f160": "10日涨跌幅",
            "f174": "10日主力净流入-净额",
            "f175": "10日主力净流入-净占比",
            "f260": "10日主力净流入最大股",
        },
    },
}


def industry_realtime(force: bool = False) -> pd.DataFrame:
    cached = None if force else _read_ttl("industry_realtime", "latest")
    if cached is not None:
        return cached
    out = _normalize_industry_realtime(_raw_industry_realtime())
    _write_ttl("industry_realtime", "latest", out)
    return out


def industry_fund_flow(period: str = "今日", force: bool = False) -> pd.DataFrame:
    if period not in FUND_FLOW_SPECS:
        raise ValueError("period must be one of 今日, 5日, 10日")
    cached = None if force else _read_ttl("industry_fund_flow", period)
    if cached is not None:
        return cached
    out = _normalize_industry_fund_flow(_raw_industry_fund_flow(period), period)
    _write_ttl("industry_fund_flow", period, out)
    return out


def industry_cons(sector: str, force: bool = False) -> pd.DataFrame:
    key = _safe_key(sector)
    cached = None if force else _read_ttl("industry_cons", key)
    if cached is not None:
        return cached
    out = _normalize_industry_cons(_raw_industry_cons(sector), sector)
    _write_ttl("industry_cons", key, out)
    return out


def industry_hist(sector: str, start: str, end: str, force: bool = False) -> pd.DataFrame:
    key = f"{_safe_key(sector)}_{start}_{end}"
    hit = None if force else cache.read(CACHE_SOURCE, "industry_hist", key)
    if hit is not None:
        return hit
    out = _normalize_industry_hist(_raw_industry_hist(sector, start, end), sector)
    cache.write(CACHE_SOURCE, "industry_hist", key, out)
    return out


def market_spot(force: bool = False) -> pd.DataFrame:
    cached = None if force else _read_ttl("market_spot", "latest")
    if cached is not None:
        return cached
    out = _normalize_market_spot(_raw_market_spot())
    _write_ttl("market_spot", "latest", out)
    return out


def _raw_industry_realtime() -> pd.DataFrame:
    fields = ",".join(INDUSTRY_REALTIME_COLS)
    return _eastmoney_clist(
        fields=fields,
        fs="m:90 t:2 f:!50",
        fid="f3",
        rename_map=INDUSTRY_REALTIME_COLS,
    )


def _raw_industry_fund_flow(period: str) -> pd.DataFrame:
    spec = FUND_FLOW_SPECS[period]
    fields = ",".join(["f12", *spec["fields"].keys()])
    return _eastmoney_clist(
        fields=fields,
        fs="m:90 t:2",
        fid=str(spec["fid"]),
        rename_map=spec["fields"],
        extra_params={"stat": spec["stat"], "fid0": spec["fid"]},
    )


def _raw_market_spot() -> pd.DataFrame:
    fields = ",".join(MARKET_SPOT_COLS)
    return _eastmoney_clist(
        fields=fields,
        fs="m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
        fid="f12",
        rename_map=MARKET_SPOT_COLS,
    )


def _raw_industry_cons(sector: str) -> pd.DataFrame:
    code = _sector_code(sector)
    fields = ",".join(CONS_COLS)
    return _eastmoney_clist(
        fields=fields,
        fs=f"b:{code} f:!50",
        fid="f3",
        rename_map=CONS_COLS,
    )


def _raw_industry_hist(sector: str, start: str, end: str) -> pd.DataFrame:
    code = _sector_code(sector)
    params = {
        "secid": f"90.{code}",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "0",
        "beg": start,
        "end": end,
        "smplmt": "10000",
        "lmt": "1000000",
    }
    data = _request_json(KLINE_URL, params)
    rows = data.get("data", {}).get("klines", [])
    out = pd.DataFrame([item.split(",") for item in rows])
    if out.empty:
        return pd.DataFrame()
    out.columns = [
        "日期",
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "振幅",
        "涨跌幅",
        "涨跌额",
        "换手率",
    ]
    return out


def _eastmoney_clist(
    fields: str,
    fs: str,
    fid: str,
    rename_map: dict[str, str],
    extra_params: dict | None = None,
    page_size: int = 100,
) -> pd.DataFrame:
    params = {
        "pn": "1",
        "pz": str(page_size),
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": fid,
        "fs": fs,
        "fields": fields,
    }
    if extra_params:
        params.update(extra_params)

    first = _request_json(CLIST_URL, params)
    data = first.get("data") or {}
    total = int(data.get("total") or 0)
    rows = list(data.get("diff") or [])
    total_pages = max(1, (total + page_size - 1) // page_size)
    for page in range(2, total_pages + 1):
        params["pn"] = str(page)
        page_data = _request_json(CLIST_URL, params).get("data") or {}
        rows.extend(page_data.get("diff") or [])
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=list(rename_map.values()))
    return frame.rename(columns=rename_map)[list(rename_map.values())]


def _request_json(url: str, params: dict) -> dict:
    response = requests.get(url, params=params, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.json()


def _normalize_industry_realtime(raw: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=raw.index)
    out["sector"] = _text(raw, "板块名称")
    out["sector_code"] = _text(raw, "板块代码")
    out["pct_chg"] = _num(raw, "涨跌幅")
    out["amount"] = _num(raw, "成交额")
    out["main_net_inflow"] = _num(raw, "主力净流入-净额")
    out["total_mv"] = _num(raw, "总市值")
    out["turnover"] = _num(raw, "换手率")
    out["up_count"] = _num(raw, "上涨家数")
    out["down_count"] = _num(raw, "下跌家数")
    out["leading_stock"] = _text(raw, "领涨股票")
    out["leading_stock_pct_chg"] = _num(raw, "领涨股票-涨跌幅")
    out["snapshot_time"] = _now_iso()
    out["data_source"] = "eastmoney"
    return out.reset_index(drop=True)


def _normalize_industry_fund_flow(raw: pd.DataFrame, period: str) -> pd.DataFrame:
    out = pd.DataFrame(index=raw.index)
    out["sector"] = _text(raw, "名称")
    out["period"] = period
    out["pct_chg"] = _num(raw, f"{period}涨跌幅")
    out["main_net_inflow"] = _num(raw, f"{period}主力净流入-净额")
    out["main_net_inflow_pct"] = _num(raw, f"{period}主力净流入-净占比")
    out["main_inflow_leader"] = _text(raw, f"{period}主力净流入最大股")
    out["snapshot_time"] = _now_iso()
    out["data_source"] = "eastmoney"
    return out.reset_index(drop=True)


def _normalize_market_spot(raw: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=raw.index)
    out["code"] = _text(raw, "代码").str.zfill(6)
    out["name"] = _text(raw, "名称")
    out["latest_price"] = _num(raw, "最新价")
    out["pct_chg"] = _num(raw, "涨跌幅")
    out["amount"] = _num(raw, "成交额")
    out["turnover"] = _num(raw, "换手率")
    out["volume_ratio"] = _num(raw, "量比")
    out["pe_ttm"] = _num(raw, "市盈率-动态")
    out["pb"] = _num(raw, "市净率")
    out["total_mv"] = _num(raw, "总市值")
    out["circ_mv"] = _num(raw, "流通市值")
    out["snapshot_time"] = _now_iso()
    out["data_source"] = "eastmoney"
    return out.reset_index(drop=True)


def _normalize_industry_cons(raw: pd.DataFrame, sector: str) -> pd.DataFrame:
    out = _normalize_market_spot(raw)
    out.insert(0, "sector", sector)
    return out


def _normalize_industry_hist(raw: pd.DataFrame, sector: str) -> pd.DataFrame:
    out = pd.DataFrame(index=raw.index)
    out["sector"] = sector
    out["trade_date"] = _text(raw, "日期")
    out["open"] = _num(raw, "开盘")
    out["close"] = _num(raw, "收盘")
    out["high"] = _num(raw, "最高")
    out["low"] = _num(raw, "最低")
    out["pct_chg"] = _num(raw, "涨跌幅")
    out["amount"] = _num(raw, "成交额")
    out["turnover"] = _num(raw, "换手率")
    return out.reset_index(drop=True)


def _sector_code(sector: str) -> str:
    panel = industry_realtime()
    matched = panel.loc[panel["sector"] == sector, "sector_code"]
    if matched.empty:
        raise ValueError(f"unknown eastmoney sector: {sector}")
    return str(matched.iloc[0])


def _read_ttl(dataset: str, key: str) -> pd.DataFrame | None:
    hit = cache.read(CACHE_SOURCE, dataset, key)
    if hit is None or CACHE_TS_COL not in hit.columns or hit.empty:
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
    payload[CACHE_TS_COL] = _now_iso()
    cache.write(CACHE_SOURCE, dataset, key, payload)


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(pd.NA, index=frame.index, dtype="Float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _text(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype="string")
    return frame[column].fillna("").astype(str)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_key(value: str) -> str:
    parsed = urlparse(f"key:///{value}")
    return parsed.path.strip("/").replace("/", "_").replace("\\", "_") or "unknown"
