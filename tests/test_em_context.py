import pandas as pd

from src.data import em_context as ctx


def test_northbound_flow_normalizes_and_caches(tmp_path, monkeypatch):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    calls = {"count": 0}
    raw = pd.DataFrame(
        {
            "交易日": ["2026-06-16"],
            "类型": ["沪港通"],
            "板块": ["沪股通"],
            "资金方向": ["北向"],
            "交易状态": [3],
            "成交净买额": [1.2],
            "资金净流入": [0.8],
            "当日资金余额": [420.0],
            "上涨数": [661],
            "持平数": [14],
            "下跌数": [852],
            "相关指数": ["上证指数"],
            "指数涨跌幅": [-0.11],
        }
    )

    def fake_raw():
        calls["count"] += 1
        return raw

    monkeypatch.setattr(ctx, "_raw_northbound_flow", fake_raw)

    first = ctx.northbound_flow()
    second = ctx.northbound_flow()

    assert calls["count"] == 1
    assert {"trade_date", "board", "direction", "net_buy_amount", "fund_net_inflow"} <= set(first.columns)
    assert first.loc[0, "board"] == "沪股通"
    assert first.loc[0, "net_buy_amount"] == 1.2
    pd.testing.assert_frame_equal(first, second)


def test_dragon_tiger_normalizes_real_columns(tmp_path, monkeypatch):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    raw = pd.DataFrame(
        {
            "代码": ["688001"],
            "名称": ["华兴源创"],
            "上榜日": ["2026-06-16"],
            "解读": ["机构买入"],
            "收盘价": [32.1],
            "涨跌幅": [9.8],
            "龙虎榜净买额": [5e7],
            "龙虎榜买入额": [8e7],
            "龙虎榜卖出额": [3e7],
            "龙虎榜成交额": [11e7],
            "市场总成交额": [20e7],
            "净买额占总成交比": [25.0],
            "成交额占总成交比": [55.0],
            "换手率": [12.3],
            "流通市值": [2e10],
            "上榜原因": ["有价格涨跌幅限制的日收盘价格涨幅达到15%的前五只证券"],
            "上榜后1日": [1.1],
            "上榜后2日": [2.2],
            "上榜后5日": [3.3],
            "上榜后10日": [4.4],
        }
    )
    monkeypatch.setattr(ctx, "_raw_dragon_tiger", lambda date: raw)

    got = ctx.dragon_tiger("20260616")

    assert got.loc[0, "code"] == "688001"
    assert got.loc[0, "trade_date"] == "2026-06-16"
    assert got.loc[0, "net_buy"] == 5e7
    assert got.loc[0, "reason"].startswith("有价格涨跌幅限制")


def test_research_reports_normalizes_real_columns(tmp_path, monkeypatch):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    raw = pd.DataFrame(
        {
            "股票代码": ["601688"],
            "股票简称": ["华泰证券"],
            "报告名称": ["AI赋能转型"],
            "东财评级": ["增持"],
            "机构": ["国信证券"],
            "近一月个股研报数": [3],
            "行业": ["证券Ⅱ"],
            "日期": ["2026-04-30"],
            "报告PDF链接": ["https://example.test/report.pdf"],
        }
    )
    monkeypatch.setattr(ctx, "_raw_research_reports", lambda symbol: raw)

    got = ctx.research_reports("601688")

    assert got.loc[0, "symbol"] == "601688"
    assert got.loc[0, "name"] == "华泰证券"
    assert got.loc[0, "title"] == "AI赋能转型"
    assert got.loc[0, "rating"] == "增持"
    assert got.loc[0, "pdf_url"].endswith("report.pdf")


def test_stock_news_uses_python_string_compat_and_normalizes(tmp_path, monkeypatch):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    seen = {}

    def fake_stock_news(symbol):
        seen["infer_string"] = pd.options.future.infer_string
        return pd.DataFrame(
            {
                "关键词": [symbol],
                "新闻标题": ["华泰证券新闻"],
                "新闻内容": ["非银金融资金流入"],
                "发布时间": ["2026-06-12 16:57:00"],
                "文章来源": ["证券时报网"],
                "新闻链接": ["http://finance.eastmoney.com/a/test.html"],
            }
        )

    monkeypatch.setattr(ctx.ak, "stock_news_em", fake_stock_news)

    got = ctx.stock_news("601688")

    assert seen["infer_string"] is False
    assert got.loc[0, "symbol"] == "601688"
    assert got.loc[0, "title"] == "华泰证券新闻"
    assert got.loc[0, "source"] == "证券时报网"
