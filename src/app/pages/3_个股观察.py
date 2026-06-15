import streamlit as st

from src.app.Home import get_panel, get_stock_panel
from src.app.ui import (
    apply_theme,
    format_amount,
    format_money_yi,
    format_percent,
    format_signed_percent,
    note,
)


st.set_page_config(page_title="个股观察", layout="wide")
apply_theme()
st.title("个股观察")

sector_panel = get_panel()
stock_panel = get_stock_panel()

left, mid, right = st.columns([1.2, 1, 1])
sector_options = ["全部"] + sorted(stock_panel["sector"].unique().tolist())
sector = left.selectbox("板块", sector_options)
role = mid.selectbox("分层", ["全部", "市值龙头", "中军", "跟随观察"])
leader_only = right.toggle("只看 Top3 龙头", value=False)

filtered = stock_panel.copy()
if sector != "全部":
    filtered = filtered[filtered["sector"] == sector]
if role != "全部" and "stock_role" in filtered.columns:
    filtered = filtered[filtered["stock_role"] == role]
if leader_only:
    filtered = filtered[filtered["is_top_leader"]]
for column in [
    "stock_role",
    "momentum_flag",
    "latest_close",
    "pct_chg",
    "amount",
    "turnover_rate",
    "volume_ratio",
    "pe_ttm",
    "pb",
]:
    if column not in filtered.columns:
        filtered[column] = None

summary_cols = st.columns(4)
summary_cols[0].metric("当前筛选", f"{len(filtered)} 只")
summary_cols[1].metric("涉及板块", f"{filtered['sector'].nunique()} 个")
summary_cols[2].metric("异动股票", f"{int(filtered['momentum_flag'].fillna(False).sum())} 只")
summary_cols[3].metric("市值合计", format_money_yi(filtered["market_cap"].sum()))

if sector != "全部":
    row = sector_panel.loc[sector]
    note(f"{sector}: {row.get('action_hint', row.get('state_note', ''))}")

table = filtered[
    [
        "sector",
        "rank",
        "symbol",
        "name",
        "stock_role",
        "momentum_flag",
        "latest_close",
        "pct_chg",
        "amount",
        "turnover_rate",
        "volume_ratio",
        "pe_ttm",
        "pb",
        "market_cap",
        "sector_share",
        "sector_state",
    ]
].copy()
table["pct_chg"] = table["pct_chg"].map(format_signed_percent)
table["amount"] = table["amount"].map(format_amount)
table["sector_share"] = table["sector_share"].map(format_percent)
table = table.rename(
    columns={
        "sector": "板块",
        "rank": "排名",
        "symbol": "代码",
        "name": "股票",
        "stock_role": "分层",
        "momentum_flag": "异动",
        "latest_close": "收盘",
        "pct_chg": "涨跌",
        "amount": "成交额",
        "turnover_rate": "换手",
        "volume_ratio": "量比",
        "pe_ttm": "PE",
        "pb": "PB",
        "market_cap": "市值(亿)",
        "sector_share": "板块占比",
        "sector_state": "阶段",
    }
)
st.dataframe(table, width="stretch", height=560)
