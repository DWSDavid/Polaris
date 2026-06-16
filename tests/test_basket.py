import pandas as pd

from src.data import basket


def test_save_load_basket(tmp_path):
    basket.BASKET_PATH = tmp_path / "basket.json"

    basket.save_basket(["证券", "电子"])

    assert basket.load_basket() == ["证券", "电子"]


def test_evaluate_basket_flags_negative_corr_and_margin_impact():
    panel = pd.DataFrame(
        {
            "sector": ["证券", "电子"],
            "state": ["主升扩散", "低位修复"],
            "trend_days": [6, 2],
            "turning_point": [False, True],
        }
    )
    corr = pd.DataFrame(
        [[1.0, -0.8], [-0.8, 1.0]],
        index=["证券", "电子"],
        columns=["证券", "电子"],
    )
    account = {"total_assets": 3143.0, "debt": 1860.0, "basket_buy_amount": 200.0}

    result = basket.evaluate_basket(["证券", "电子"], panel, corr, account)

    assert result["hedge_score"] > 0.5
    assert ["证券", "电子"] in result["hedge_pairs"] or ["电子", "证券"] in result["hedge_pairs"]
    assert "对冲" in result["verdict"]
    assert result["guarantee_after"] > 0
    assert result["per_item"][0]["sector"] == "证券"
    assert result["per_item"][1]["turning_point"] is True
