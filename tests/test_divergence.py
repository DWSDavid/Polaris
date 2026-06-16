import pandas as pd

from src.compute.divergence import (
    correlation_matrix,
    has_correlation_coverage,
    hedge_pairs,
    hedge_score,
    structural_hedge_pairs,
)


def test_negative_corr_detected():
    rets = pd.DataFrame(
        {"证券": [1, -1, 1, -1, 1.0], "电子": [-1, 1, -1, 1, -1.0]}
    )

    corr = correlation_matrix(rets)

    assert corr.loc["证券", "电子"] < -0.5
    assert hedge_score(["证券", "电子"], corr) > 0.5
    assert ["证券", "电子"] in hedge_pairs(["证券", "电子"], corr, threshold=-0.3) or [
        "电子",
        "证券",
    ] in hedge_pairs(["证券", "电子"], corr, threshold=-0.3)


def test_correlation_coverage_requires_all_selected_pairs():
    corr = pd.DataFrame([[1.0]], index=["证券"], columns=["证券"])

    assert has_correlation_coverage(["证券", "电子"], corr) is False


def test_structural_hedge_pairs_detects_defensive_vs_growth_when_corr_missing():
    assert structural_hedge_pairs(["证券Ⅱ", "电子"]) == [["证券Ⅱ", "电子"]]
