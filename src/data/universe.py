"""Universe loading helpers."""

from pathlib import Path

import pandas as pd

_COLMAP = {
    "板块": "sector",
    "排名": "rank",
    "代码": "code",
    "完整代码": "symbol",
    "股票名称": "name",
    "交易所": "exchange",
    "总市值(亿元)": "market_cap",
    "指数权重(%)": "index_weight",
    "占板块总市值": "sector_share",
}


def load_universe(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="板块Top10")
    df = df.rename(columns=_COLMAP)
    df["code"] = df["code"].astype(str).str.zfill(6)
    df["market_cap"] = pd.to_numeric(df["market_cap"], errors="coerce")
    df["index_weight"] = pd.to_numeric(df["index_weight"], errors="coerce")
    df["sector_share"] = pd.to_numeric(df["sector_share"], errors="coerce")
    df["leader_type"] = "market_cap"
    cols = [
        "sector",
        "rank",
        "code",
        "symbol",
        "name",
        "exchange",
        "market_cap",
        "index_weight",
        "sector_share",
        "leader_type",
    ]
    return df[cols].reset_index(drop=True)


def add_momentum_leader(
    df: pd.DataFrame,
    sector: str,
    code: str,
    symbol: str,
    name: str,
) -> pd.DataFrame:
    new = {
        "sector": sector,
        "rank": None,
        "code": str(code).zfill(6),
        "symbol": symbol,
        "name": name,
        "exchange": symbol[:2],
        "market_cap": None,
        "leader_type": "momentum",
    }
    return pd.concat([df, pd.DataFrame([new])], ignore_index=True)
