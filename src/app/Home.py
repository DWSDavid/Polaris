import plotly.express as px
import streamlit as st

from src.pipeline.refresh import refresh_eod, stock_panel


@st.cache_data(ttl=600)
def get_panel():
    return refresh_eod()


@st.cache_data(ttl=600)
def get_stock_panel():
    return stock_panel()


def render_home():
    st.set_page_config(page_title="Polaris 北极星", layout="wide")
    st.title("Polaris 北极星 · 大盘云图")

    panel = get_panel()
    stocks = get_stock_panel()
    metric_cols = st.columns(4)
    metric_cols[0].metric("覆盖板块", f"{len(panel)} 个")
    metric_cols[1].metric("观察股票", f"{len(stocks)} 只")
    metric_cols[2].metric("Top3 龙头", f"{int(stocks['is_top_leader'].sum())} 只")
    metric_cols[3].metric(
        "数据口径",
        "股票池结构" if panel["data_quality"].eq("seed_static").all() else "收盘行情",
    )

    fig = px.treemap(
        panel.reset_index(names="sector"),
        path=["sector"],
        values="total_market_cap",
        color="strength",
        color_continuous_scale="RdYlGn",
        hover_data=["state", "stock_count", "top_leaders", "coverage"],
        custom_data=["state", "top_leaders"],
    )
    fig.update_traces(texttemplate="%{label}<br>%{customdata[0]}<br>%{customdata[1]}")
    st.plotly_chart(fig, width="stretch")

    st.subheader("状态说明")
    st.dataframe(
        panel[["state", "strength_rank", "stock_count", "top_leaders", "state_note"]],
        width="stretch",
    )


if __name__ == "__main__":
    render_home()
