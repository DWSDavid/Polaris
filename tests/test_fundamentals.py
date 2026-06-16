import pandas as pd

from src.compute.fundamentals import sector_valuation_snapshot


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
