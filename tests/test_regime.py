import pandas as pd

from src.research.regime import detect_epochs, dominant_theme, macro_context, style_spread


def test_style_spread_and_epoch():
    big = pd.Series([100, 101, 102, 103, 104.0])
    small = pd.Series([100, 100, 99, 98, 97.0])

    spread = style_spread(big, small)
    epochs = detect_epochs(spread)

    assert spread.iloc[-1] > 0
    assert len(epochs) >= 1
    assert epochs[-1]["regime"] == "大盘占优"


def test_detect_epochs_splits_when_style_sign_flips():
    spread = pd.Series([-0.03, -0.02, 0.01, 0.03, -0.01], index=pd.date_range("2026-01-01", periods=5))

    epochs = detect_epochs(spread)

    assert [item["regime"] for item in epochs] == ["小盘占优", "大盘占优", "小盘占优"]
    assert epochs[1]["start"] == pd.Timestamp("2026-01-03")


def test_dominant_theme_returns_epoch_leaders():
    timeline = pd.DataFrame(
        {
            "week": ["2026-01", "2026-01", "2026-02", "2026-02"],
            "sector": ["电子", "银行", "电子", "银行"],
            "strength": [3.0, 1.0, 4.0, 2.0],
            "main_net_inflow": [10.0, 1.0, 20.0, 2.0],
        }
    )
    epoch = {"start": "2026-01", "end": "2026-02"}

    theme = dominant_theme(timeline, epoch, top_n=2)

    assert theme[0]["sector"] == "电子"
    assert theme[0]["avg_strength"] > theme[1]["avg_strength"]


def test_macro_context_joins_mocked_rate_northbound_and_margin(monkeypatch):
    from src.research import regime

    monkeypatch.setattr(
        regime,
        "_fetch_cn_10y",
        lambda: pd.DataFrame({"date": ["2026-01-01"], "cn_10y": [2.1]}),
    )
    monkeypatch.setattr(
        regime,
        "_fetch_northbound",
        lambda: pd.DataFrame({"date": ["2026-01-01"], "northbound_net": [12.0]}),
    )
    monkeypatch.setattr(
        regime,
        "_fetch_margin",
        lambda: pd.DataFrame({"date": ["2026-01-01"], "margin_balance": [18000.0]}),
    )

    got = macro_context("2026-01-01", "2026-01-31")

    assert got.loc[0, "cn_10y"] == 2.1
    assert got.loc[0, "northbound_net"] == 12.0
    assert got.loc[0, "margin_balance"] == 18000.0
