import plotly.express as px
import streamlit as st

from src.app.ui import apply_theme, format_percent, note, risk_label
from src.pipeline.refresh import refresh_eod, stock_panel


@st.cache_data(ttl=600)
def get_panel():
    return refresh_eod()


@st.cache_data(ttl=600)
def get_stock_panel():
    return stock_panel()


def render_home():
    st.set_page_config(page_title="Polaris 北极星", layout="wide")
    apply_theme()
    st.title("Polaris 北极星")

    panel = get_panel()
    stocks = get_stock_panel()
    signals_confirmed = panel.get("signals_confirmed", False)
    signals_confirmed = (
        bool(signals_confirmed.fillna(False).all())
        if hasattr(signals_confirmed, "fillna")
        else False
    )
    if signals_confirmed:
        trade_date = "-"
        if "trade_date" in panel.columns and panel["trade_date"].notna().any():
            trade_date = str(panel["trade_date"].dropna().max())
        st.success(f"已接入收盘行情 · 交易日 {trade_date}")
    else:
        st.warning("行情未确认：当前展示的是股票池静态结构兜底，不是实时轮动信号。")

    top_sector = panel.sort_values("strength", ascending=False).iloc[0]
    note(
        f"先看 {top_sector.name}: {top_sector['state']}。"
        f"风险 {risk_label(top_sector.get('risk_level'))}，"
        f"{top_sector.get('action_hint', top_sector.get('state_note', ''))}"
    )
    metric_cols = st.columns(4)
    metric_cols[0].metric("覆盖板块", f"{len(panel)} 个")
    metric_cols[1].metric("观察股票", f"{len(stocks)} 只")
    metric_cols[2].metric("Top3 龙头", f"{int(stocks['is_top_leader'].sum())} 只")
    metric_cols[3].metric(
        "数据口径",
        "股票池结构" if panel["data_quality"].eq("seed_static").all() else "收盘行情",
    )

    st.subheader("板块云图")
    market_ready = (
        signals_confirmed
        and "amount" in panel.columns
        and panel["amount"].fillna(0).sum() > 0
    )
    value_col = "amount" if market_ready else "total_market_cap"
    color_col = (
        "avg_pct_chg" if market_ready and "avg_pct_chg" in panel.columns else "strength"
    )
    color_scale = "RdYlGn" if market_ready else "Tealgrn"
    fig = px.treemap(
        panel.reset_index(names="sector"),
        path=["sector"],
        values=value_col,
        color=color_col,
        color_continuous_scale=color_scale,
        hover_data=["state", "stock_count", "top_leaders", "coverage"],
        custom_data=["state", "top_leaders"],
    )
    fig.update_traces(texttemplate="%{label}<br>%{customdata[0]}<br>%{customdata[1]}")
    st.plotly_chart(fig, width="stretch")

    st.subheader("先读这张表")
    summary = panel[
        [
            "state",
            "strength_rank",
            "risk_level",
            "stock_count",
            "top_leaders",
            "action_hint",
            "watch_points",
        ]
    ].copy()
    summary["strength_rank"] = summary["strength_rank"].map(format_percent)
    summary["risk_level"] = summary["risk_level"].map(risk_label)
    summary = summary.rename(
        columns={
            "state": "阶段",
            "strength_rank": "强度分位",
            "risk_level": "风险",
            "stock_count": "股票数",
            "top_leaders": "前三龙头",
            "action_hint": "动作提示",
            "watch_points": "观察点",
        }
    )
    st.dataframe(summary, width="stretch", height=420)


if __name__ == "__main__":
    render_home()
