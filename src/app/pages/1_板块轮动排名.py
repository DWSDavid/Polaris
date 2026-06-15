import streamlit as st

from src.app.Home import get_panel, get_stock_panel
from src.app.ui import (
    apply_theme,
    format_amount,
    format_money_yi,
    format_percent,
    format_signed_percent,
    note,
    risk_label,
)


st.set_page_config(page_title="板块轮动排名", layout="wide")
apply_theme()
st.title("板块轮动排名")

panel = get_panel().sort_values("strength", ascending=False)
stocks = get_stock_panel()
leader = panel.iloc[0]
note(
    f"先看 {leader.name}: {leader['state']}，风险 {risk_label(leader.get('risk_level'))}。"
    f"{leader.get('action_hint', '')}"
)

overview = panel[
    [
        "state",
        "strength_rank",
        "risk_level",
        "stock_count",
        "total_market_cap",
        "coverage",
        "leader_contrib",
        "top_leaders",
        "action_hint",
        "watch_points",
    ]
].copy()
overview["strength_rank"] = overview["strength_rank"].map(format_percent)
overview["risk_level"] = overview["risk_level"].map(risk_label)
overview["total_market_cap"] = overview["total_market_cap"].map(format_money_yi)
overview["coverage"] = overview["coverage"].map(format_percent)
overview["leader_contrib"] = overview["leader_contrib"].map(format_percent)
overview = overview.rename(
    columns={
        "state": "阶段",
        "strength_rank": "强度分位",
        "risk_level": "风险",
        "stock_count": "股票数",
        "total_market_cap": "Top10总市值",
        "coverage": "Top10覆盖",
        "leader_contrib": "Top3集中",
        "top_leaders": "前三龙头",
        "action_hint": "动作提示",
        "watch_points": "观察点",
    }
)
st.dataframe(overview, width="stretch", height=420)
st.caption("风险级别不是买卖信号，只是提醒你应该先检查扩散、龙头贡献和担保比。")

sector = st.selectbox("查看板块成分", list(panel.index))
sector_stocks = stocks[stocks["sector"] == sector].copy()
for column in ["latest_close", "pct_chg", "amount", "volume_ratio"]:
    if column not in sector_stocks.columns:
        sector_stocks[column] = None
sector_stocks["pct_chg"] = sector_stocks["pct_chg"].map(format_signed_percent)
sector_stocks["amount"] = sector_stocks["amount"].map(format_amount)
sector_stocks["sector_share"] = sector_stocks["sector_share"].map(format_percent)
sector_stocks = sector_stocks[
    [
        "rank",
        "symbol",
        "name",
        "stock_role",
        "momentum_flag",
        "latest_close",
        "pct_chg",
        "amount",
        "volume_ratio",
        "market_cap",
        "sector_share",
        "sector_state",
    ]
].rename(
    columns={
        "rank": "排名",
        "symbol": "代码",
        "name": "股票",
        "stock_role": "分层",
        "momentum_flag": "异动",
        "latest_close": "收盘",
        "pct_chg": "涨跌",
        "amount": "成交额",
        "volume_ratio": "量比",
        "market_cap": "市值(亿)",
        "sector_share": "板块占比",
        "sector_state": "板块阶段",
    }
)
st.subheader(f"{sector} · 成分股")
st.dataframe(sector_stocks, width="stretch", height=430)
