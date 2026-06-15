import streamlit as st

from src.app.Home import get_panel, get_stock_panel


st.set_page_config(page_title="板块轮动排名", layout="wide")
st.title("板块轮动排名")

panel = get_panel().sort_values("strength", ascending=False)
stocks = get_stock_panel()

overview = panel[
    [
        "state",
        "strength",
        "strength_rank",
        "stock_count",
        "total_market_cap",
        "coverage",
        "leader_contrib",
        "top_leaders",
        "state_note",
    ]
].rename(
    columns={
        "state": "阶段",
        "strength": "强度分",
        "strength_rank": "强度分位",
        "stock_count": "股票数",
        "total_market_cap": "Top10总市值(亿元)",
        "coverage": "Top10覆盖度",
        "leader_contrib": "Top3集中度",
        "top_leaders": "前三龙头",
        "state_note": "解释",
    }
)
st.dataframe(overview, width="stretch")
st.caption("当前强度来自股票池静态结构；收盘行情接入后会替换为涨跌、成交额和资金流。")

sector = st.selectbox("查看板块成分", list(panel.index))
sector_stocks = stocks[stocks["sector"] == sector].copy()
sector_stocks = sector_stocks[
    [
        "rank",
        "code",
        "symbol",
        "name",
        "leader_badge",
        "market_cap",
        "index_weight",
        "sector_share",
        "sector_state",
    ]
].rename(
    columns={
        "rank": "排名",
        "code": "代码",
        "symbol": "完整代码",
        "name": "股票名称",
        "leader_badge": "角色",
        "market_cap": "市值(亿元)",
        "index_weight": "指数权重(%)",
        "sector_share": "板块占比",
        "sector_state": "板块阶段",
    }
)
st.subheader(f"{sector} · Top10 成分股")
st.dataframe(sector_stocks, width="stretch")
