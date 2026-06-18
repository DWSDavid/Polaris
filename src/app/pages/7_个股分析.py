from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.ai.stock_advice import stock_advice
from src.app.ui import apply_theme, hero, metric_grid, page_intro, plotly_template, section, state_badge, status_line
from src.compute.stock_decision import evaluate_stock_setup
from src.data import em_client
from src.pipeline.stock_analysis import build_stock_analysis_payload


DEFAULT_CODE = "601688"
DEFAULT_SECTOR = "证券"


@st.cache_data(ttl=600)
def get_stock_payload(
    query: str,
    sector: str,
    holding: dict | None,
    include_context: bool,
    include_history: bool,
) -> dict:
    return build_stock_analysis_payload(
        query=query,
        sector_hint=sector,
        holding=holding,
        include_context=include_context,
        include_history=include_history,
    )


@st.cache_data(ttl=600)
def get_sector_options() -> list[str]:
    try:
        realtime = em_client.industry_realtime()
    except Exception:
        return [DEFAULT_SECTOR]
    if realtime.empty or "sector" not in realtime.columns:
        return [DEFAULT_SECTOR]
    sectors = realtime["sector"].dropna().astype(str).drop_duplicates().tolist()
    return sectors or [DEFAULT_SECTOR]


def render_page() -> None:
    st.set_page_config(page_title="Polaris 个股分析", layout="wide")
    apply_theme()
    page_intro(
        "这页回答：发现一只股票后，当前节点是适合观察入场、继续持有，还是该降低仓位假设。",
        "怎么用：输入股票代码或名称，选择所属细分行业；系统会把个股量价资金和行业主线放在一起看。",
    )

    sectors = get_sector_options()
    default_sector_index = _default_sector_index(sectors)
    cols = st.columns([1.1, 1.1, 0.8, 0.8, 0.8, 0.8])
    query = cols[0].text_input("股票代码或名称", value=DEFAULT_CODE)
    sector = cols[1].selectbox("所属细分行业", sectors, index=default_sector_index)
    has_holding = cols[2].toggle("作为持仓分析", value=True)
    cost = cols[3].number_input("持仓成本", min_value=0.0, value=0.0, step=0.01)
    include_history = cols[4].toggle("加载日线资金", value=False)
    include_context = cols[5].toggle("加载研报新闻", value=False)
    holding = {"cost": cost, "shares": 1} if has_holding and cost > 0 else None

    try:
        payload = get_stock_payload(query.strip(), sector, holding, include_context, include_history)
        load_error = None
    except Exception as exc:
        payload = {"facts": {}, "decision": {}, "daily": pd.DataFrame(), "flow": pd.DataFrame(), "context": {}}
        load_error = exc

    facts = payload.get("facts", {})
    decision = facts.get("decision") or payload.get("decision") or {}
    if not facts:
        status_line("个股分析暂不可用")
        if load_error:
            st.error(f"个股分析失败：{load_error}")
        hero("个股分析", "当前没有拿到可用个股数据。不要用空结论判断。", "单股节点 / 行业 context / 风控")
        return

    status_line(f"东财 + AKShare · {payload.get('as_of', '')} · AI 只解释真实数值")
    st.markdown(state_badge(str(decision.get("stance", "观察等待确认"))), unsafe_allow_html=True)
    ai_text = _safe_stock_advice(facts)
    hero(
        f"个股分析：{facts.get('name') or facts.get('code')}",
        ai_text,
        "TradingAgents-style / 技术面 / 资金面 / 行业背景 / 风控",
    )
    metric_grid(
        [
            ("系统倾向", str(decision.get("stance", "-"))),
            ("综合分", f"{float(decision.get('score', 0) or 0):.2f}"),
            ("最新价", f"{float(facts.get('latest_price', 0) or 0):.2f}"),
            ("箱体位置", _position_label(facts.get("position_in_box"))),
            ("5日主力", _money_label(facts.get("stock_inflow_5d"), signed=True)),
            ("行业状态", str(facts.get("sector_state", "未知"))),
        ]
    )

    decision_tab, technical_tab, money_tab, pattern_tab, context_tab, ai_tab = st.tabs(
        ["决策摘要", "技术面", "资金面", "历史陷阱", "行业背景", "AI 与架构"]
    )
    with decision_tab:
        _render_decision(decision)
    with technical_tab:
        _render_technical(payload.get("daily", pd.DataFrame()), facts)
    with money_tab:
        _render_flow(payload.get("flow", pd.DataFrame()), facts)
    with pattern_tab:
        _render_pattern_risk(facts)
    with context_tab:
        _render_context(payload)
    with ai_tab:
        _render_ai_architecture(facts, ai_text)


def _render_decision(decision: dict) -> None:
    section("决策摘要", "把入场/持有/退出倾向拆成理由、风险和下一步验证条件。")
    cols = st.columns(3)
    cols[0].metric("倾向", str(decision.get("stance", "-")))
    cols[1].metric("综合分", f"{float(decision.get('score', 0) or 0):.2f}")
    cols[2].metric("风险数", str(len(decision.get("risk_flags") or [])))
    st.subheader("理由")
    st.write("、".join(decision.get("reasons") or ["缺少足够共振，先观察"]))
    st.subheader("风险")
    risks = decision.get("risk_flags") or ["暂无明显结构性风险"]
    for risk in risks:
        if risk == "暂无明显结构性风险":
            st.info(risk)
        else:
            st.warning(risk)
    st.subheader("今日观察")
    st.write("；".join(decision.get("watch_points") or []))


def _render_technical(daily: pd.DataFrame, facts: dict) -> None:
    section("技术面", "看价格是否仍在中期结构内，而不是只看今天涨跌。")
    if daily.empty:
        st.info("日线暂未加载或接口暂不可用；打开顶部“加载日线资金”后再看均线和箱体。")
        return
    plot = daily.copy()
    date_col = "date" if "date" in plot.columns else "trade_date"
    plot[date_col] = pd.to_datetime(plot[date_col], errors="coerce")
    plot["ma20"] = pd.to_numeric(plot["close"], errors="coerce").rolling(20, min_periods=1).mean()
    plot["ma60"] = pd.to_numeric(plot["close"], errors="coerce").rolling(60, min_periods=1).mean()
    long = plot.tail(120).melt(id_vars=[date_col], value_vars=["close", "ma20", "ma60"])
    fig = px.line(long, x=date_col, y="value", color="variable")
    plotly_template(fig)
    fig.update_layout(height=380, legend_title_text="")
    st.plotly_chart(fig, width="stretch")
    metric_grid(
        [
            ("20日涨跌", _pct_label(facts.get("return_20d"))),
            ("60日涨跌", _pct_label(facts.get("return_60d"))),
            ("60日回撤", f"{float(facts.get('drawdown_60d', 0) or 0):.1%}"),
            ("60日均线", _above_label(facts.get("above_ma60"))),
        ]
    )


def _render_flow(flow: pd.DataFrame, facts: dict) -> None:
    section("资金面", "看个股资金是否跟行业资金同向，避免只被价格脉冲带走。")
    metric_grid(
        [
            ("最近主力", _money_label(facts.get("stock_inflow_latest"), signed=True)),
            ("5日主力", _money_label(facts.get("stock_inflow_5d"), signed=True)),
            ("10日主力", _money_label(facts.get("stock_inflow_10d"), signed=True)),
            ("行业10日", _money_label(facts.get("sector_inflow_10d"), signed=True)),
        ]
    )
    if flow.empty or "main_net_inflow" not in flow.columns:
        st.info("个股资金流暂未加载或接口暂不可用；打开顶部“加载日线资金”后再看资金 Track。")
        return
    plot = flow.tail(60).copy()
    date_col = "date" if "date" in plot.columns else plot.columns[0]
    plot[date_col] = pd.to_datetime(plot[date_col], errors="coerce")
    plot["main_net_inflow_yi"] = pd.to_numeric(plot["main_net_inflow"], errors="coerce") / 100_000_000
    fig = px.bar(
        plot,
        x=date_col,
        y="main_net_inflow_yi",
        color="main_net_inflow_yi",
        color_continuous_scale="RdYlGn",
    )
    plotly_template(fig)
    fig.update_layout(height=360, coloraxis_showscale=False)
    st.plotly_chart(fig, width="stretch")


def _render_pattern_risk(facts: dict) -> None:
    section(
        "历史陷阱",
        "检测下跌后的快速反弹是否像历史上的诱多样本：价格反抽、仍在60日线下、资金没有跟上时要更谨慎。",
    )
    pattern = facts.get("pattern_risk") or {}
    report = facts.get("historical_trap") or {}
    if not pattern:
        st.info("打开顶部“加载日线资金”后，系统会用日线和资金流检测疑似诱多风险。")
        return

    metric_grid(
        [
            ("当前模式", str(pattern.get("label", "未判断"))),
            ("风险分", f"{float(pattern.get('risk_score', 0) or 0):.2f}"),
            ("历史样本", f"{int(float(report.get('sample_count', 0) or 0))} 个"),
            ("5日中位收益", f"{float(report.get('median_forward_return_5d', 0) or 0):+.1%}"),
            ("5日胜率", f"{float(report.get('win_rate_5d', 0) or 0):.0%}"),
        ]
    )
    reasons = pattern.get("reasons") or []
    if reasons:
        st.subheader("触发原因")
        st.write("、".join(str(reason) for reason in reasons))
    st.subheader("历史参考")
    st.write(report.get("summary", "历史相似样本不足，暂时不能下结论。"))
    st.caption("这是风险分布，不是买卖指令；真正操作仍要等价格、资金、行业主线同时验证。")


def _render_context(payload: dict) -> None:
    section("行业背景", "把单股放回行业阶段、龙虎榜、研报和新闻里看。")
    facts = payload.get("facts", {})
    sector = payload.get("sector_panel", pd.DataFrame())
    if not sector.empty:
        st.dataframe(sector.head(1), width="stretch", height=120)
    cols = st.columns(2)
    context = payload.get("context", {})
    if not context:
        st.info("研报、新闻、龙虎榜属于慢数据，默认不加载；打开顶部“加载研报新闻”后再看佐证。")
    with cols[0]:
        st.subheader("研报")
        research = context.get("research", pd.DataFrame())
        if research.empty:
            st.info("研报暂不可用。")
        else:
            columns = [col for col in ["date", "title", "rating", "org"] if col in research.columns]
            st.dataframe(research[columns].head(8), width="stretch", height=240)
    with cols[1]:
        st.subheader("新闻")
        news = context.get("news", pd.DataFrame())
        if news.empty:
            st.info("新闻暂不可用。")
        else:
            columns = [col for col in ["publish_time", "title", "source"] if col in news.columns]
            st.dataframe(news[columns].head(8), width="stretch", height=240)
    st.caption(
        f"龙虎榜活跃：{'是' if facts.get('dragon_tiger_active') else '否'}；"
        "这些只是佐证，不替代量价和行业结构。"
    )


def _render_ai_architecture(facts: dict, ai_text: str) -> None:
    section("AI 与架构", "当前是 TradingAgents-style 的单次 grounded brief；后续可接真实多智能体 runner。")
    st.write(ai_text)
    st.dataframe(
        pd.DataFrame(
            [
                {"角色": "技术面", "读取": "均线、箱体、20/60日涨跌、回撤"},
                {"角色": "资金面", "读取": "个股5/10日主力、行业10日资金"},
                {"角色": "行业背景", "读取": "行业状态、趋势持续、龙头与细分方向"},
                {"角色": "风控", "读取": "跌破60日线、超过10%回撤、高位放量、资金流出"},
            ]
        ),
        width="stretch",
        height=180,
        hide_index=True,
    )


def _safe_stock_advice(facts: dict) -> str:
    try:
        return stock_advice(facts, timeout=8)
    except Exception:
        return (
            f"结论：{facts.get('name', '该股')}当前系统倾向是"
            f"{facts.get('decision', {}).get('stance', '观察等待确认')}，只作观察辅助，人最后决定。"
        )


def _default_sector_index(sectors: list[str]) -> int:
    if DEFAULT_SECTOR in sectors:
        return sectors.index(DEFAULT_SECTOR)
    for index, sector in enumerate(sectors):
        if DEFAULT_SECTOR in str(sector):
            return index
    return 0


def _money_label(value, signed: bool = False) -> str:
    try:
        number = 0.0 if pd.isna(value) else float(value)
    except (TypeError, ValueError):
        number = 0.0
    yi = number / 100_000_000 if abs(number) >= 1_000_000 else number
    prefix = "+" if signed and yi > 0 else ""
    return f"{prefix}{yi:.2f} 亿"


def _pct_label(value) -> str:
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "-"


def _position_label(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.5
    if number >= 0.9:
        return "高位"
    if number >= 0.65:
        return "偏高"
    if number <= 0.25:
        return "低位"
    return "中部"


def _above_label(value) -> str:
    if value is None:
        return "缺数据"
    return "之上" if bool(value) else "之下"


if __name__ == "__main__":
    render_page()
