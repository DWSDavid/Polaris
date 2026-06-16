import pandas as pd

from src.compute.divergence import correlation_matrix, hedge_pairs, hedge_score


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
