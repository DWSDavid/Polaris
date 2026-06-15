import streamlit as st

from src.app.Home import get_panel, get_stock_panel


st.set_page_config(page_title="个股观察", layout="wide")
st.title("个股观察")

sector_panel = get_panel()
stock_panel = get_stock_panel()

left, right = st.columns([1, 1])
sector_options = ["全部"] + sorted(stock_panel["sector"].unique().tolist())
sector = left.selectbox("板块", sector_options)
leader_only = right.toggle("只看 Top3 龙头", value=False)

filtered = stock_panel.copy()
if sector != "全部":
    filtered = filtered[filtered["sector"] == sector]
if leader_only:
    filtered = filtered[filtered["is_top_leader"]]

summary_cols = st.columns(4)
summary_cols[0].metric("当前筛选", f"{len(filtered)} 只")
summary_cols[1].metric("涉及板块", f"{filtered['sector'].nunique()} 个")
summary_cols[2].metric("Top3 龙头", f"{int(filtered['is_top_leader'].sum())} 只")
summary_cols[3].metric("市值合计", f"{filtered['market_cap'].sum():,.0f} 亿")

table = filtered[
    [
        "sector",
        "rank",
        "code",
        "symbol",
        "name",
        "leader_badge",
        "market_cap",
        "index_weight",
        "sector_share",
        "sector_strength_rank",
        "sector_state",
        "sector_state_note",
    ]
].rename(
    columns={
        "sector": "板块",
        "rank": "排名",
        "code": "代码",
        "symbol": "完整代码",
        "name": "股票名称",
        "leader_badge": "角色",
        "market_cap": "市值(亿元)",
        "index_weight": "指数权重(%)",
        "sector_share": "板块占比",
        "sector_strength_rank": "板块强度分位",
        "sector_state": "板块阶段",
        "sector_state_note": "阶段解释",
    }
)
st.dataframe(table, width="stretch")

if sector != "全部":
    st.subheader(f"{sector} 板块摘要")
    row = sector_panel.loc[sector]
    st.write(row["state_note"])
    st.write(f"前三龙头: {row['top_leaders']}")
