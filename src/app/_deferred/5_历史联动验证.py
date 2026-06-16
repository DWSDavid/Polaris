import pandas as pd
import streamlit as st

from src.compute import linkage_stats


st.set_page_config(page_title="历史联动验证", layout="wide")
st.title("历史联动验证")

st.caption("当前为统计口径演示页；接入历史行情缓存后，输入会替换为真实龙头和板块序列。")

leader_daily = pd.DataFrame(
    {
        "trade_date": ["20260601", "20260602", "20260603", "20260604"],
        "pct_chg": [0.5, 5.2, 1.0, 2.0],
        "volume_ratio": [1.0, 2.1, 1.2, 1.1],
    }
)
sector_daily = pd.DataFrame(
    {
        "trade_date": ["20260601", "20260602", "20260603", "20260604"],
        "close": [100.0, 102.0, 105.0, 106.0],
    }
)
benchmark_daily = pd.DataFrame(
    {
        "trade_date": ["20260601", "20260602", "20260603", "20260604"],
        "close": [100.0, 101.0, 102.0, 103.0],
    }
)

events = linkage_stats.detect_leader_events(leader_daily)
forward = linkage_stats.forward_excess_returns(
    events["trade_date"].tolist(),
    sector_daily,
    benchmark_daily,
    horizons=[1, 2],
)
summary = linkage_stats.summarize_linkage_stats(forward, horizons=[1, 2])

st.subheader("事件")
st.dataframe(events, width="stretch")
st.subheader("T+N 超额收益")
st.dataframe(forward, width="stretch")
st.subheader("汇总")
st.json(summary)

st.caption(f"事件识别函数: {linkage_stats.detect_leader_events.__name__}")
st.caption(f"汇总函数: {linkage_stats.summarize_linkage_stats.__name__}")
