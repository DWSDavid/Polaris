import plotly.express as px
import streamlit as st

from src.app.ui import apply_theme, format_percent, hero, metric_grid, note, status_line
from src.compute.ai_brief import generate_ai_brief, has_ai_key
from src.compute.market_intelligence import (
    build_ai_context,
    hedge_alerts,
    sector_diagnostics,
)
from src.compute.rotation_history import summarize_sector_track
from src.pipeline.refresh import (
    refresh_eod,
    sector_history_panel,
    stock_history_panel,
    stock_panel,
)
from src.pipeline.realtime import safe_realtime_industry_panel


@st.cache_data(ttl=600)
def get_panel():
    return refresh_eod()


@st.cache_data(ttl=600)
def get_stock_panel():
    return stock_panel()


@st.cache_data(ttl=600)
def get_sector_history():
    return sector_history_panel()


@st.cache_data(ttl=600)
def get_stock_history():
    return stock_history_panel()


@st.cache_data(ttl=600)
def get_realtime_industries():
    return safe_realtime_industry_panel(timeout_seconds=8)


def render_home():
    st.set_page_config(page_title="Polaris 北极星", layout="wide")
    apply_theme()

    panel = get_panel()
    stocks = get_stock_panel()
    history = get_sector_history()
    stock_history = get_stock_history()
    realtime_industries, realtime_error = get_realtime_industries()
    diagnostics = sector_diagnostics(panel, stocks)
    alerts = hedge_alerts(diagnostics)
    ai_context = build_ai_context(diagnostics, alerts)
    top_sector = diagnostics.iloc[0]
    signals_confirmed = _signals_confirmed(panel)

    status_line(_status_text(panel, signals_confirmed))
    if realtime_error:
        st.warning(f"实时行业快照拉取失败，正在显示上次缓存：{realtime_error}")
    hero(
        f"先看 {top_sector['sector']}，再检查对冲",
        top_sector["brief"],
        "大趋势 / 资金 / 分化 / 龙头联动",
    )

    metric_grid(
        [
            ("今日主线", str(top_sector["sector"])),
            (
                "资金方向",
                f"{top_sector['money_direction']} {top_sector['fund_flow_yi']:+.1f}亿",
            ),
            ("1-3周趋势", str(top_sector["trend_label"])),
            ("对冲警报", f"{len(alerts)} 条"),
        ]
    )

    if alerts:
        note(alerts[0]["message"])
    elif not signals_confirmed:
        note("当前是静态股票池兜底：先看结构，不要把状态标签当成真实买卖信号。")

    market_tab, radar_tab, flow_tab, history_tab, leader_tab, ai_tab = st.tabs(
        ["大盘云图", "板块雷达", "资金/趋势", "历史跟踪", "龙头展开", "AI 总结"]
    )
    with market_tab:
        _render_market_treemap(realtime_industries)
    with radar_tab:
        _render_sector_radar(diagnostics)
    with flow_tab:
        _render_flow_map(diagnostics)
    with history_tab:
        _render_history_track(history)
    with leader_tab:
        _render_leader_expanders(diagnostics, stocks, stock_history)
    with ai_tab:
        _render_ai_tab(ai_context)


def _signals_confirmed(panel) -> bool:
    signals = panel.get("signals_confirmed", False)
    if hasattr(signals, "fillna"):
        return bool(signals.fillna(False).all())
    return False


def _status_text(panel, signals_confirmed: bool) -> str:
    if signals_confirmed:
        trade_date = "-"
        if "trade_date" in panel.columns and panel["trade_date"].notna().any():
            trade_date = str(panel["trade_date"].dropna().max())
        return f"行情已确认：收盘数据 · 交易日 {trade_date}"
    return "行情未确认：当前展示股票池静态结构兜底，不是实时轮动信号。"


def _render_sector_radar(diagnostics):
    view = diagnostics[
        [
            "sector",
            "sector_group",
            "state",
            "fund_flow_yi",
            "diffusion",
            "trend_label",
            "split_label",
            "valuation_label",
            "valuation_coverage",
            "median_pe_ttm",
            "leader_line",
            "brief",
        ]
    ].rename(
        columns={
            "sector": "板块",
            "sector_group": "风格",
            "state": "阶段",
            "fund_flow_yi": "资金(亿)",
            "diffusion": "扩散",
            "trend_label": "1-3周趋势",
            "split_label": "分化",
            "valuation_label": "估值",
            "valuation_coverage": "估值覆盖",
            "median_pe_ttm": "PE中位",
            "leader_line": "龙头",
            "brief": "判断",
        }
    )
    st.dataframe(
        view,
        width="stretch",
        height=430,
        column_config={
            "资金(亿)": st.column_config.NumberColumn(format="%+.1f"),
            "扩散": st.column_config.ProgressColumn(
                min_value=0,
                max_value=1,
                format="%.0f%%",
            ),
            "估值覆盖": st.column_config.ProgressColumn(
                min_value=0,
                max_value=1,
                format="%.0f%%",
            ),
            "PE中位": st.column_config.NumberColumn(format="%.1f"),
        },
    )


def _render_market_treemap(realtime_industries):
    if realtime_industries.empty:
        st.info(
            "暂无实时行业快照。AKShare 接口恢复后，这里会显示东财行业板块大盘云图。"
        )
        return

    panel = realtime_industries.copy()
    value_col = "total_mv" if panel["total_mv"].fillna(0).sum() > 0 else "up_count"
    fig = px.treemap(
        panel,
        path=["industry"],
        values=value_col,
        color="pct_chg",
        color_continuous_scale="RdYlGn",
        hover_data=[
            "pct_chg",
            "fund_flow_yi",
            "diffusion",
            "turnover_rate",
            "leading_stock",
            "leading_stock_pct_chg",
        ],
        custom_data=[
            "pct_chg",
            "fund_flow_yi",
            "diffusion",
            "leading_stock",
        ],
    )
    fig.update_traces(
        texttemplate=(
            "%{label}<br>"
            "%{customdata[0]:+.2f}% · %{customdata[1]:+.1f}亿<br>"
            "扩散 %{customdata[2]:.0%} · %{customdata[3]}"
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#f2efe4",
        height=560,
        margin=dict(t=8, l=0, r=0, b=0),
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "大小=行业总市值，颜色=实时涨跌幅；标签里的资金为东财行业资金流今日主力净流入。"
    )


def _render_flow_map(diagnostics):
    fig = px.scatter(
        diagnostics,
        x="fund_flow_yi",
        y="diffusion",
        size="leader_contrib",
        color="sector_group",
        hover_name="sector",
        hover_data=["state", "trend_label", "split_label", "leader_line"],
        color_discrete_map={
            "growth": "#86c98a",
            "old_economy": "#e0b45a",
            "cyclical": "#8fb8d8",
        },
        labels={
            "fund_flow_yi": "资金净流入(亿)",
            "diffusion": "扩散率",
            "sector_group": "风格",
        },
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#f2efe4",
        height=460,
    )
    fig.update_xaxes(gridcolor="#33402f", zerolinecolor="#d66a5d")
    fig.update_yaxes(gridcolor="#33402f", tickformat=".0%")
    st.plotly_chart(fig, width="stretch")
    note("横轴看钱往哪走，纵轴看板块内部有多少股票一起动；气泡越大，越依赖前三个龙头。")


def _render_history_track(history):
    if history.empty:
        st.info(
            "还没有可用的历史轨迹缓存。运行一次 AKShare/Tushare 行情刷新后，这里会显示过去几天/几周的资金和扩散变化。"
        )
        return

    summary = summarize_sector_track(history).rename(
        columns={
            "sector": "板块",
            "fund_flow_5d": "5日资金",
            "fund_flow_15d": "15日资金",
            "positive_days_15d": "15日强势天数",
            "current_positive_streak": "当前连强",
            "latest_diffusion": "最新扩散",
            "track_label": "轨迹判断",
        }
    )
    st.dataframe(
        summary,
        width="stretch",
        height=280,
        column_config={
            "5日资金": st.column_config.NumberColumn(format="%+.0f"),
            "15日资金": st.column_config.NumberColumn(format="%+.0f"),
            "最新扩散": st.column_config.ProgressColumn(
                min_value=0,
                max_value=1,
                format="%.0f%%",
            ),
        },
    )

    sectors = sorted(history["sector"].dropna().unique().tolist())
    selected = st.selectbox("选择板块查看轨迹", sectors)
    selected_history = history[history["sector"] == selected].sort_values("trade_date")
    fig = px.line(
        selected_history,
        x="trade_date",
        y=["fund_flow", "diffusion"],
        markers=True,
        labels={"value": "资金/扩散", "trade_date": "交易日", "variable": "指标"},
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#f2efe4",
        height=380,
    )
    fig.update_xaxes(gridcolor="#33402f")
    fig.update_yaxes(gridcolor="#33402f")
    st.plotly_chart(fig, width="stretch")


def _render_leader_expanders(diagnostics, stocks, stock_history):
    for _, sector in diagnostics.head(8).iterrows():
        title = (
            f"{sector['sector']} · {sector['trend_label']} · "
            f"{sector['money_direction']} {sector['fund_flow_yi']:+.1f}亿"
        )
        with st.expander(title, expanded=False):
            st.write(sector["brief"])
            leader_rows = (
                stocks[stocks["sector"] == sector["sector"]]
                .sort_values("rank")
                .head(10)
            )
            for column in [
                "pct_chg",
                "amount",
                "volume_ratio",
                "trend20",
                "consecutive_up",
                "stock_role",
            ]:
                if column not in leader_rows.columns:
                    leader_rows[column] = None
            table = leader_rows[
                [
                    "rank",
                    "symbol",
                    "name",
                    "stock_role",
                    "pct_chg",
                    "amount",
                    "volume_ratio",
                    "trend20",
                    "consecutive_up",
                ]
            ].rename(
                columns={
                    "rank": "排名",
                    "symbol": "代码",
                    "name": "股票",
                    "stock_role": "角色",
                    "pct_chg": "涨跌%",
                    "amount": "成交额",
                    "volume_ratio": "量比",
                    "trend20": "20日趋势",
                    "consecutive_up": "连涨",
                }
            )
            st.dataframe(
                table,
                width="stretch",
                height=280,
                column_config={
                    "涨跌%": st.column_config.NumberColumn(format="%+.2f%%"),
                    "成交额": st.column_config.NumberColumn(format="%.0f"),
                    "量比": st.column_config.NumberColumn(format="%.2f"),
                },
            )
            _render_stock_history_chart(sector["sector"], leader_rows, stock_history)


def _render_stock_history_chart(sector_name: str, leader_rows, stock_history):
    if stock_history.empty:
        st.caption("暂无个股历史缓存；刷新行情后会显示最近走势。")
        return
    sector_history = stock_history[stock_history["sector"] == sector_name].copy()
    if sector_history.empty:
        st.caption("这个板块暂无个股历史缓存。")
        return
    options = leader_rows[["symbol", "name"]].drop_duplicates()
    labels = {
        f"{row.symbol} {row.name}": row.symbol
        for row in options.itertuples()
        if row.symbol in set(sector_history["symbol"])
    }
    if not labels:
        st.caption("这个板块的龙头暂无历史序列。")
        return
    selected_label = st.selectbox(
        "选择个股走势",
        list(labels.keys()),
        key=f"stock-history-{sector_name}",
    )
    selected = sector_history[
        sector_history["symbol"] == labels[selected_label]
    ].sort_values("trade_date")
    fig = px.line(
        selected,
        x="trade_date",
        y=["close", "pct_chg", "amount"],
        markers=True,
        labels={"value": "数值", "trade_date": "交易日", "variable": "指标"},
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#f2efe4",
        height=320,
    )
    fig.update_xaxes(gridcolor="#33402f")
    fig.update_yaxes(gridcolor="#33402f")
    st.plotly_chart(fig, width="stretch")


def _render_ai_tab(ai_context: str):
    st.caption(
        "DeepSeek 默认用于快速总结和解释；模型只会基于 Polaris 给出的结构化上下文，不会补写未提供的新闻或财务数据。"
    )
    provider_options = {"DeepSeek 快速总结": "deepseek", "ChatGPT 备用": "openai"}
    provider_label = st.radio(
        "AI 引擎",
        list(provider_options.keys()),
        horizontal=True,
        label_visibility="collapsed",
    )
    provider = provider_options[provider_label]
    with st.expander("解释口径", expanded=False):
        st.markdown("""
            - 冷启动：实时/EOD 数据还没接上时，只能展示股票池结构，不能当买卖信号。
            - 扩散：行业里上涨股票占比，越高说明不是单一龙头在硬拉。
            - 主力分化：行业涨但主力资金流出，或只靠少数龙头贡献，后续持续性要打折。
            - 对冲：成长和老经济方向相反时，组合收益可能互相抵消。
            - 噪声过滤：Polaris 只展开行业龙头和领先公司，不追每天新冒出来的小票。
            """)
    if not has_ai_key(provider):
        env_name = "DEEPSEEK_API_KEY" if provider == "deepseek" else "OPENAI_API_KEY"
        st.warning(
            f"未检测到 {env_name}。设置到 .env 或系统环境变量后，这里会生成 AI 总结。"
        )
        return
    if st.button(f"生成 {provider_label.split()[0]} 分析", type="primary"):
        with st.spinner("生成中"):
            try:
                st.write(generate_ai_brief(ai_context, provider=provider))
            except Exception as exc:
                st.error(f"{provider_label.split()[0]} 请求失败：{exc}")


if __name__ == "__main__":
    render_home()
