import pandas as pd

from src.compute.fundamentals import sector_valuation_snapshot, valuation_guard


def test_sector_valuation_snapshot_labels_median_pe_and_coverage():
    stocks = pd.DataFrame(
        {
            "sector": ["金融", "金融", "信息技术", "信息技术"],
            "pe_ttm": [6.0, 8.0, 45.0, None],
            "pb": [0.7, 0.9, 5.0, None],
        }
    )

    snapshot = sector_valuation_snapshot(stocks)
    finance = snapshot[snapshot["sector"] == "金融"].iloc[0]
    growth = snapshot[snapshot["sector"] == "信息技术"].iloc[0]

    assert finance["median_pe_ttm"] == 7.0
    assert finance["valuation_coverage"] == 1.0
    assert finance["valuation_label"] == "低估值"
    assert growth["valuation_coverage"] == 0.5
    assert growth["valuation_label"] == "高估值"


def test_sector_valuation_snapshot_handles_missing_data():
    stocks = pd.DataFrame({"sector": ["金融"], "pe_ttm": [None], "pb": [None]})

    snapshot = sector_valuation_snapshot(stocks)

    assert snapshot.iloc[0]["valuation_label"] == "估值缺数据"
    assert snapshot.iloc[0]["valuation_coverage"] == 0.0


def test_sector_valuation_snapshot_handles_missing_columns():
    stocks = pd.DataFrame(
        {
            "sector": ["金融", "金融"],
            "symbol": ["SH600000", "SH601688"],
            "name": ["浦发银行", "华泰证券"],
        }
    )

    snapshot = sector_valuation_snapshot(stocks)

    assert snapshot.iloc[0]["sector"] == "金融"
    assert snapshot.iloc[0]["valuation_label"] == "估值缺数据"
    assert snapshot.iloc[0]["valuation_coverage"] == 0.0


def test_valuation_guard_flags_high_valuation_and_missing_data():
    high = valuation_guard(
        {"sector": "电子", "median_pe_ttm": 52.0, "valuation_coverage": 0.9}
    )
    missing = valuation_guard(
        {"sector": "证券", "median_pe_ttm": None, "valuation_coverage": 0.0}
    )
    ok = valuation_guard(
        {"sector": "银行", "median_pe_ttm": 8.0, "valuation_coverage": 0.9}
    )

    assert high["level"] == "yellow"
    assert "高估值" in high["message"]
    assert missing["level"] == "unknown"
    assert ok["level"] == "green"
