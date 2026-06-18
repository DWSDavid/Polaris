import pandas as pd

from src.pipeline import stock_analysis as sa


def test_stock_payload_uses_sector_constituents_before_full_market(monkeypatch):
    monkeypatch.setattr(
        sa.em_client,
        "industry_cons",
        lambda sector: pd.DataFrame(
            {
                "sector": [sector],
                "code": ["601688"],
                "name": ["华泰证券"],
                "latest_price": [19.7],
                "pct_chg": [2.1],
                "amount": [2_000_000_000],
                "volume_ratio": [1.4],
            }
        ),
    )
    monkeypatch.setattr(
        sa.em_client,
        "market_spot",
        lambda: (_ for _ in ()).throw(AssertionError("full market should be fallback")),
    )
    monkeypatch.setattr(
        sa.akshare_client,
        "daily_hist",
        lambda symbol, start, end: pd.DataFrame(
            {
                "date": pd.date_range("2026-04-01", periods=70).strftime("%Y-%m-%d"),
                "close": [10 + i * 0.1 for i in range(70)],
                "amount": [1e9] * 70,
                "pct": [1.0] * 70,
            }
        ),
    )
    monkeypatch.setattr(
        sa.akshare_client,
        "individual_fund_flow",
        lambda symbol: pd.DataFrame({"main_net_inflow": [10_000_000] * 10}),
    )
    monkeypatch.setattr(
        sa,
        "_sector_panel",
        lambda sector, start, end, *args, **kwargs: pd.DataFrame(
            {
                "sector": [sector],
                "state": ["主升扩散"],
                "inflow_10d": [2_000_000_000],
                "main_net_inflow": [300_000_000],
                "pct_chg": [1.1],
            }
        ),
    )
    monkeypatch.setattr(sa, "_stock_context", lambda symbol: {"dragon_tiger": pd.DataFrame(), "research": pd.DataFrame(), "news": pd.DataFrame()})

    payload = sa.build_stock_analysis_payload("601688", "证券")

    assert payload["facts"]["name"] == "华泰证券"
    assert payload["facts"]["code"] == "601688"


def test_stock_payload_skips_slow_news_and_research_context_by_default(monkeypatch):
    monkeypatch.setattr(
        sa.em_client,
        "industry_cons",
        lambda sector: pd.DataFrame(
            {"sector": [sector], "code": ["601688"], "name": ["华泰证券"], "latest_price": [19.7]}
        ),
    )
    monkeypatch.setattr(sa, "_sector_panel", lambda sector, start, end, *args, **kwargs: pd.DataFrame({"sector": [sector], "state": ["主升扩散"]}))
    monkeypatch.setattr(sa.akshare_client, "daily_hist", lambda symbol, start, end: pd.DataFrame())
    monkeypatch.setattr(sa.akshare_client, "individual_fund_flow", lambda symbol: pd.DataFrame())
    monkeypatch.setattr(
        sa,
        "_stock_context",
        lambda symbol: (_ for _ in ()).throw(AssertionError("slow context should be opt-in")),
    )

    payload = sa.build_stock_analysis_payload("601688", "证券")

    assert payload["context"] == {}
    assert payload["facts"]["name"] == "华泰证券"


def test_stock_payload_skips_akshare_history_by_default(monkeypatch):
    monkeypatch.setattr(
        sa.em_client,
        "industry_cons",
        lambda sector: pd.DataFrame(
            {"sector": [sector], "code": ["601688"], "name": ["华泰证券"], "latest_price": [19.7]}
        ),
    )
    monkeypatch.setattr(sa, "_sector_panel", lambda sector, start, end, *args, **kwargs: pd.DataFrame({"sector": [sector], "state": ["主升扩散"]}))
    monkeypatch.setattr(
        sa.akshare_client,
        "daily_hist",
        lambda symbol, start, end: (_ for _ in ()).throw(AssertionError("history should be opt-in")),
    )
    monkeypatch.setattr(
        sa.akshare_client,
        "individual_fund_flow",
        lambda symbol: (_ for _ in ()).throw(AssertionError("flow should be opt-in")),
    )

    payload = sa.build_stock_analysis_payload("601688", "证券")

    assert payload["daily"].empty
    assert payload["flow"].empty


def test_match_sector_name_accepts_eastmoney_suffixes():
    realtime = pd.DataFrame({"sector": ["证券Ⅲ", "证券Ⅱ", "银行"]})

    assert sa._match_sector_name(realtime, "证券") == "证券Ⅲ"
    assert sa._match_sector_name(realtime, "银行") == "银行"


def test_sector_panel_skips_industry_history_unless_requested(monkeypatch):
    monkeypatch.setattr(
        sa.em_client,
        "industry_realtime",
        lambda: pd.DataFrame(
            {
                "sector": ["证券Ⅲ"],
                "pct_chg": [1.2],
                "amount": [2_000_000_000],
                "main_net_inflow": [100_000_000],
                "up_count": [8],
                "down_count": [2],
            }
        ),
    )
    monkeypatch.setattr(
        sa.em_client,
        "industry_fund_flow",
        lambda period: pd.DataFrame({"sector": ["证券Ⅲ"], "main_net_inflow": [200_000_000]}),
    )
    monkeypatch.setattr(
        sa.em_client,
        "industry_hist",
        lambda sector, start, end: (_ for _ in ()).throw(AssertionError("history should be opt-in")),
    )

    panel = sa._sector_panel("证券Ⅲ", "20260301", "20260618", include_history=False)

    assert not panel.empty
    assert panel.iloc[0]["sector"] == "证券Ⅲ"
