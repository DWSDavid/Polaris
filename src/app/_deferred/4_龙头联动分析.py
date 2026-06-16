import streamlit as st

from src.app.Home import get_panel, get_stock_panel
from src.compute import linkage_stats


st.set_page_config(page_title="龙头联动分析", layout="wide")
st.title("龙头联动分析")

sector_panel = get_panel()
stock_panel = get_stock_panel()

sector = st.selectbox("板块", list(sector_panel.index))
sector_stocks = stock_panel[stock_panel["sector"] == sector].copy()
leaders = sector_stocks[sector_stocks["rank"] <= 3].copy()

st.subheader(f"{sector} · 龙头组")
leader_cols = [
    "rank",
    "symbol",
    "name",
    "stock_role",
    "momentum_flag",
    "pct_chg",
    "amount",
    "volume_ratio",
    "sector_share",
]
for column in leader_cols:
    if column not in leaders.columns:
        leaders[column] = None
st.dataframe(
    leaders[leader_cols].rename(
        columns={
            "rank": "排名",
            "symbol": "完整代码",
            "name": "股票名称",
            "stock_role": "个股分层",
            "momentum_flag": "人气异动",
            "pct_chg": "涨跌幅(%)",
            "amount": "成交额",
            "volume_ratio": "量比",
            "sector_share": "板块占比",
        }
    ),
    width="stretch",
)

row = sector_panel.loc[sector]
st.subheader("联动判断")
st.write(row["action_hint"] if "action_hint" in row else row["state_note"])
st.write("V2 统计口径: 龙头放量大涨事件 -> 板块 T+1/T+3/T+5 超额收益。")
st.write("当前页面先展示龙头组和所需字段；历史序列缓存接入后会调用 linkage_stats 生成真实胜率。")
st.caption(f"统计函数入口: {linkage_stats.detect_leader_events.__name__}")
