from pathlib import Path

from src.data.universe import load_universe


SEED = Path("data/universe/sector_leaders_seed.xlsx")


def test_load_universe_schema():
    df = load_universe(SEED)
    assert {
        "sector",
        "code",
        "symbol",
        "name",
        "exchange",
        "market_cap",
        "index_weight",
        "sector_share",
        "leader_type",
    } <= set(df.columns)
    assert len(df) == 110
    assert df["leader_type"].eq("market_cap").all()

    row = df[df["code"] == "600519"].iloc[0]
    assert row["sector"] == "主要消费"
    assert row["symbol"] == "SH600519"
    assert row["index_weight"] > 0
    assert row["sector_share"] > 0
