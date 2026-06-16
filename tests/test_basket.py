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


def test_evaluate_basket_uses_structural_fallback_when_corr_missing():
    panel = pd.DataFrame(
        {
            "sector": ["证券Ⅱ", "电子"],
            "state": ["冷启动", "低位修复"],
            "trend_days": [0, 0],
            "turning_point": [False, False],
        }
    )

    result = basket.evaluate_basket(["证券", "电子"], panel, pd.DataFrame(), {})

    assert result["hedge_score"] > 0.5
    assert result["hedge_source"] == "structural_fallback"
    assert result["hedge_pairs"] == [["证券Ⅱ", "电子"]]
    assert "红色结构性对冲预警" in result["verdict"]


def test_evaluate_basket_reports_uncertain_when_corr_missing_without_structural_pair():
    panel = pd.DataFrame(
        {
            "sector": ["证券Ⅱ", "银行"],
            "state": ["冷启动", "低位修复"],
            "trend_days": [0, 0],
            "turning_point": [False, False],
        }
    )

    result = basket.evaluate_basket(["证券", "银行"], panel, pd.DataFrame(), {})

    assert result["hedge_score"] == 0.0
    assert result["hedge_source"] == "unavailable"
    assert "历史相关性暂不可用" in result["verdict"]
