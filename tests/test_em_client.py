import pandas as pd

from src.data import em_client as em


def test_industry_realtime_cached(tmp_path, monkeypatch):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    fake = pd.DataFrame(
        {
            "板块名称": ["银行", "电子"],
            "板块代码": ["BK0475", "BK1036"],
            "涨跌幅": [1.2, -0.8],
            "成交额": [3e10, 5e10],
            "主力净流入-净额": [2e8, -1e8],
            "上涨家数": [28, 12],
            "下跌家数": [10, 42],
            "领涨股票": ["招商银行", "立讯精密"],
        }
    )
    calls = {"count": 0}

    def fake_raw():
        calls["count"] += 1
        return fake

    monkeypatch.setattr(em, "_raw_industry_realtime", fake_raw)

    d1 = em.industry_realtime()
    d2 = em.industry_realtime()

    assert calls["count"] == 1
    assert {"sector", "pct_chg", "amount", "main_net_inflow"} <= set(d1.columns)
    assert d1.loc[d1["sector"] == "银行", "main_net_inflow"].iloc[0] == 2e8
    pd.testing.assert_frame_equal(d1, d2)


def test_industry_fund_flow_normalizes_period_columns(tmp_path, monkeypatch):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    fake = pd.DataFrame(
        {
            "名称": ["电力设备"],
            "10日涨跌幅": [8.8],
            "10日主力净流入-净额": [12.3e8],
            "10日主力净流入-净占比": [4.2],
            "10日主力净流入最大股": ["阳光电源"],
        }
    )
    monkeypatch.setattr(em, "_raw_industry_fund_flow", lambda period: fake)

    got = em.industry_fund_flow("10日")

    assert got.loc[0, "sector"] == "电力设备"
    assert got.loc[0, "period"] == "10日"
    assert got.loc[0, "main_net_inflow"] == 12.3e8
    assert got.loc[0, "main_inflow_leader"] == "阳光电源"


def test_market_spot_normalizes_core_columns(tmp_path, monkeypatch):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    raw = pd.DataFrame(
        {
            "代码": ["600000"],
            "名称": ["浦发银行"],
            "涨跌幅": [0.5],
            "成交额": [1.2e9],
            "换手率": [0.8],
            "总市值": [2.3e11],
            "市盈率-动态": [6.2],
            "市净率": [0.5],
        }
    )
    monkeypatch.setattr(em, "_raw_market_spot", lambda: raw)

    got = em.market_spot()

    assert got.loc[0, "code"] == "600000"
    assert got.loc[0, "name"] == "浦发银行"
    assert got.loc[0, "amount"] == 1.2e9
    assert got.loc[0, "turnover"] == 0.8
    assert got.loc[0, "total_mv"] == 2.3e11


def test_industry_cons_normalizes_leader_candidates(tmp_path, monkeypatch):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    raw = pd.DataFrame(
        {
            "代码": ["601398"],
            "名称": ["工商银行"],
            "涨跌幅": [-0.2],
            "成交额": [8e8],
            "换手率": [0.1],
            "市盈率-动态": [5.1],
            "市净率": [0.45],
        }
    )
    monkeypatch.setattr(em, "_raw_industry_cons", lambda sector: raw)

    got = em.industry_cons("银行")

    assert got.loc[0, "sector"] == "银行"
    assert got.loc[0, "code"] == "601398"
    assert got.loc[0, "name"] == "工商银行"
    assert got.loc[0, "amount"] == 8e8


def test_industry_hist_normalizes_ohlc(tmp_path, monkeypatch):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    raw = pd.DataFrame(
        {
            "日期": ["2026-06-15"],
            "开盘": [100.0],
            "收盘": [103.0],
            "最高": [104.0],
            "最低": [99.0],
            "涨跌幅": [2.5],
            "成交额": [9e9],
            "换手率": [1.3],
        }
    )
    monkeypatch.setattr(em, "_raw_industry_hist", lambda sector, start, end: raw)

    got = em.industry_hist("银行", "20260601", "20260616")

    assert got.loc[0, "sector"] == "银行"
    assert got.loc[0, "trade_date"] == "2026-06-15"
    assert got.loc[0, "close"] == 103.0
    assert got.loc[0, "amount"] == 9e9


def test_industry_fund_flow_hist_normalizes_daily_flow(tmp_path, monkeypatch):
    from src.data import cache

    cache.CACHE_DIR = tmp_path
    raw = pd.DataFrame(
        {
            "日期": ["2026-06-15"],
            "主力净流入-净额": [2.5e8],
            "主力净流入-净占比": [3.2],
            "超大单净流入-净额": [1e8],
            "大单净流入-净额": [1.5e8],
        }
    )
    monkeypatch.setattr(em, "_raw_industry_fund_flow_hist", lambda sector: raw)

    got = em.industry_fund_flow_hist("银行")

    assert got.loc[0, "sector"] == "银行"
    assert got.loc[0, "trade_date"] == "2026-06-15"
    assert got.loc[0, "main_net_inflow"] == 2.5e8
    assert got.loc[0, "main_net_inflow_pct"] == 3.2


def test_eastmoney_clist_uses_http_delay_host(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"total": 1, "diff": [{"f12": "BK0475"}]}}

    def fake_get(url, params, headers, timeout):
        calls.append(url)
        return Response()

    monkeypatch.setattr(em.requests, "get", fake_get)

    em._eastmoney_clist(
        fields="f12",
        fs="m:90 t:2 f:!50",
        fid="f3",
        rename_map={"f12": "板块代码"},
    )

    assert calls[0] == "http://push2delay.eastmoney.com/api/qt/clist/get"


def test_request_json_retries_transient_timeout(monkeypatch):
    calls = {"count": 0}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"total": 0, "diff": []}}

    def fake_get(url, params, headers, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise em.requests.Timeout("slow eastmoney page")
        return Response()

    monkeypatch.setattr(em.requests, "get", fake_get)

    assert em._request_json("http://example.test", {}) == {
        "data": {"total": 0, "diff": []}
    }
    assert calls["count"] == 2
