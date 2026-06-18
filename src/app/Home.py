from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from src.ai.summarize import summarize_sector
from src.app.ui import (
    apply_theme,
    hero,
    metric_grid,
    note,
    page_intro,
    plotly_template,
    section,
    state_badge,
    status_line,
)
from src.compute.hot_focus import build_hot_dragon_focus
from src.compute.mainline import mainline_breakdown, mainline_score, pick_mainline
from src.data import akshare_client, em_client, em_context
from src.data.sector_groups import aggregate_to_groups, filter_actionable_groups
from src.data.universe_v2 import build_universe
from src.pipeline.sector_panel_v2 import build_sector_panel_v2


@st.cache_data(ttl=600)
def get_sector_panel():
    realtime = em_client.industry_realtime()
    flow_5d = em_client.industry_fund_flow("5日")
    flow_10d = em_client.industry_fund_flow("10日")
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=45)).strftime("%Y%m%d")
    history_sectors = (
        realtime.sort_values(["pct_chg", "main_net_inflow"], ascending=False)
        .head(12)["sector"]
        .dropna()
        .tolist()
    )
    leader_sectors = (
        realtime.sort_values(["pct_chg", "main_net_inflow"], ascending=False)
        .head(20)["sector"]
        .dropna()
        .tolist()
    )
    histories = {}
    for sector in history_sectors:
        try:
            histories[sector] = em_client.industry_hist(sector, start, end)
        except Exception:
            histories[sector] = pd.DataFrame()
    leaders = _build_leaders_for_sectors(leader_sectors)
    fine_panel = build_sector_panel_v2(
        industry_realtime=realtime,
        flow_5d=flow_5d,
        flow_10d=flow_10d,
        histories=histories,
        leaders=leaders,
    )
    panel = filter_actionable_groups(aggregate_to_groups(fine_panel))
    return mainline_score(panel).sort_values(
        ["mainline_score", "strength_rank"], ascending=False
    )


@st.cache_data(ttl=600)
def get_hot_dragon_focus():
    hot = em_context.hot_rank(limit=100)
    histories = _hot_focus_histories(hot)
    try:
        dragon = em_context.dragon_tiger()
    except Exception:
        dragon = pd.DataFrame()
    return build_hot_dragon_focus(hot, dragon, top_n=100, histories=histories)


def render_home():
    st.set_page_config(page_title="Polaris 北极星", layout="wide")
    apply_theme()
    page_intro(
        "这页回答：今天大类主线是谁，资金和扩散是否支持它。",
        "怎么用：先看云图确认主线面积和颜色，再用候选表看10日资金、趋势持续和龙头，最后进下钻核对细分板块。",
    )

    try:
        panel = get_sector_panel()
        load_error = None
    except Exception as exc:
        panel = pd.DataFrame()
        load_error = exc

    if panel.empty:
        status_line("行情未接入：东财实时数据暂不可用。")
        if load_error:
            st.error(f"行情未接入：{load_error}")
        hero(
            "行情未接入",
            "当前没有可用的东财行业实时数据。不要把空页面当作行情判断。",
            "v2.0 功能版",
        )
        return

    mainline = pick_mainline(panel)
    top = panel.loc[panel["sector"] == mainline].iloc[0] if mainline else panel.iloc[0]
    decision_text = _decision_summary(top)
    status_line(f"东财实时已接入 · 行业数 {len(panel)} · 10分钟缓存")
    st.markdown(state_badge(str(top["state"])), unsafe_allow_html=True)
    hero(
        f"今日主线：{top['sector']}",
        decision_text,
        "大趋势 / 资金 / 持续天数 / 龙头",
    )
    metric_grid(
        [
            ("阶段", str(top["state"])),
            ("趋势持续", f"{int(top['trend_days'])} 天"),
            ("10日主力", f"{_yi(top['inflow_10d']):+.1f} 亿"),
            ("扩散", f"{float(top['diffusion']):.0%}"),
        ]
    )
    if bool(top.get("turning_point", False)):
        note("拐点提示：资金或动能出现转弱，先降低追高假设。")
    note(f"为什么是它：{_mainline_reason(top)}")

    market_tab, table_tab, hot_tab, ai_tab = st.tabs(
        ["大盘云图", "主线候选表", "热度龙虎榜", "AI 总结"]
    )
    with market_tab:
        section("大盘云图", "面积看成交额，颜色看涨跌，先确认主线是不是有扩散。")
        _render_market_treemap(panel)
    with table_tab:
        section("主线候选表", "中期主线分、资金和趋势持续天数放在一起看。")
        _render_candidate_table(panel)
    with hot_tab:
        section("热度龙虎榜", "东财人气前100与龙虎榜资金行为的交集，先盯不追。")
        _render_hot_dragon_focus()
    with ai_tab:
        section("AI 总结", "AI 只读取本页真实 facts，用来解释，不做自动买卖。")
        _render_ai_tab(top)


def _render_market_treemap(panel: pd.DataFrame):
    view = panel.copy()
    view["treemap_value"] = pd.to_numeric(view["amount"], errors="coerce").fillna(0)
    if view["treemap_value"].sum() <= 0:
        view["treemap_value"] = pd.to_numeric(
            view["main_net_inflow"], errors="coerce"
        ).abs().fillna(0)
    view["treemap_value"] = view["treemap_value"].clip(lower=1)
    view["label"] = view["sector"].astype(str) + " · " + view["state"].astype(str)
    fig = px.treemap(
        view,
        path=["label"],
        values="treemap_value",
        color="pct_chg",
        color_continuous_scale="RdYlGn",
        hover_data=[
            "sector",
            "state",
            "main_net_inflow",
            "inflow_10d",
            "trend_days",
            "diffusion",
            "top_leaders",
        ],
        custom_data=[
            "sector",
            "state",
            "pct_chg",
            "main_net_inflow",
            "trend_days",
            "top_leaders",
        ],
    )
    fig.update_traces(
        texttemplate=(
            "%{customdata[0]}<br>%{customdata[1]} · "
            "%{customdata[2]:+.2f}%<br>"
            "主力 %{customdata[3]:+.2s} · 持续 %{customdata[4]}天<br>"
            "%{customdata[5]}"
        )
    )
    plotly_template(fig)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#f2efe4",
        height=560,
        margin=dict(t=8, l=0, r=0, b=0),
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "大小=成交额，颜色=涨跌幅；持续天数按主导细分板块取整数，不再把多个细分行业平均成 0.7 天。"
    )


def _render_candidate_table(panel: pd.DataFrame):
    table = panel.sort_values("mainline_score", ascending=False).head(40).copy()
    table["10日净流入(亿)"] = table["inflow_10d"].map(_yi)
    table["今日主力(亿)"] = table["main_net_inflow"].map(_yi)
    table["成交额(亿)"] = table["amount"].map(_yi)
    table["trend_days"] = table["trend_days"].map(_int_days)
    table["细分板块"] = table["children"].map(_children_text) if "children" in table.columns else ""
    table = table[
        [
            "sector",
            "state",
            "trend_days",
            "10日净流入(亿)",
            "今日主力(亿)",
            "pct_chg",
            "diffusion",
            "top_leaders",
            "细分板块",
            "turning_point",
            "mainline_score",
            "成交额(亿)",
        ]
    ].rename(
        columns={
            "sector": "行业",
            "state": "状态",
            "trend_days": "已持续天数",
            "pct_chg": "涨跌幅%",
            "diffusion": "扩散",
            "top_leaders": "龙头",
            "turning_point": "拐点",
            "mainline_score": "主线分",
        }
    )
    st.dataframe(
        table,
        width="stretch",
        height=520,
        column_config={
            "10日净流入(亿)": st.column_config.NumberColumn(format="%+.1f"),
            "今日主力(亿)": st.column_config.NumberColumn(format="%+.1f"),
            "成交额(亿)": st.column_config.NumberColumn(format="%.1f"),
            "主线分": st.column_config.NumberColumn(format="%.2f"),
            "涨跌幅%": st.column_config.NumberColumn(format="%+.2f"),
            "扩散": st.column_config.ProgressColumn(
                min_value=0,
                max_value=1,
                format="%.0f%%",
            ),
        },
    )


def _render_hot_dragon_focus():
    try:
        focus = get_hot_dragon_focus()
    except Exception as exc:
        st.warning(f"东财热度/龙虎榜暂不可用：{exc}")
        return
    if focus.empty:
        st.info("东财热度榜或龙虎榜暂未返回可用观察池。")
        return

    table = focus.head(40).copy()
    table["龙虎榜净买(亿)"] = table["dragon_tiger_net_buy"].map(_yi)
    table["consecutive_up_days"] = table["consecutive_up_days"].map(_int_days)
    table["trend_days"] = table["trend_days"].map(_int_days)
    table = table[
        [
            "hot_rank",
            "focus_score",
            "code",
            "name",
            "latest_price",
            "pct_chg",
            "consecutive_up_days",
            "trend_days",
            "return_20d",
            "dragon_tiger_on_list",
            "dragon_tiger_latest_date",
            "dragon_tiger_count",
            "龙虎榜净买(亿)",
            "dragon_tiger_reasons",
            "focus_reason",
        ]
    ].rename(
        columns={
            "hot_rank": "热度排名",
            "focus_score": "观察分",
            "code": "代码",
            "name": "名称",
            "latest_price": "最新价",
            "pct_chg": "涨跌幅%",
            "consecutive_up_days": "连涨天数",
            "trend_days": "趋势持续",
            "return_20d": "20日涨跌%",
            "dragon_tiger_on_list": "龙虎榜",
            "dragon_tiger_latest_date": "龙虎榜日期",
            "dragon_tiger_count": "上榜次数",
            "dragon_tiger_reasons": "上榜原因",
            "focus_reason": "为什么盯",
        }
    )
    st.dataframe(
        table,
        width="stretch",
        height=520,
        column_config={
            "观察分": st.column_config.NumberColumn(format="%.2f"),
            "最新价": st.column_config.NumberColumn(format="%.2f"),
            "涨跌幅%": st.column_config.NumberColumn(format="%+.2f"),
            "20日涨跌%": st.column_config.NumberColumn(format="%+.2f"),
            "龙虎榜净买(亿)": st.column_config.NumberColumn(format="%+.2f"),
            "龙虎榜": st.column_config.CheckboxColumn(),
        },
    )
    st.caption(
        "热度榜=东财人气前100；龙虎榜日期显示最近可用上榜日；连涨/趋势优先补热度前12的日线，避免整页刷新过慢。这里只做重点观察池，不是买入建议。"
    )


def _render_ai_tab(top: pd.Series):
    facts = _facts(top)
    st.caption("AI 总结只接收下面这些系统算出的真实数值；无 key 时显示本地占位，不报错。")
    st.dataframe(pd.DataFrame([facts]), width="stretch", height=120)
    st.write(_decision_summary(top))


def _decision_summary(row: pd.Series) -> str:
    facts = _facts(row)
    text = summarize_sector(facts)
    if text.startswith("未配置 AI API Key"):
        return _local_summary(facts)
    return text


def _local_summary(facts: dict) -> str:
    turning = "，有拐点预警" if facts["turning_point"] else ""
    return (
        f"{facts['sector']}处于{facts['state']}，趋势已持续{facts['trend_days']}天，"
        f"10日主力净流入{facts['inflow_10d']:+.1f}亿，今日主力"
        f"{facts['main_net_inflow']:+.1f}亿，扩散{facts['diffusion']:.0%}"
        f"{turning}。先看{facts['top_leaders']}能否继续带动中军。"
    )


def _mainline_reason(row: pd.Series) -> str:
    return (
        f"10日资金 {_yi(row.get('inflow_10d', 0)):+.1f} 亿 / "
        f"持续 {int(row.get('trend_days', 0) or 0)} 天 / "
        f"扩散 {float(row.get('diffusion', 0) or 0):.0%} / "
        f"{mainline_breakdown(row)}"
    )


def _facts(row: pd.Series) -> dict:
    return {
        "sector": str(row["sector"]),
        "state": str(row["state"]),
        "trend_days": int(row.get("trend_days", 0) or 0),
        "pct_chg": round(float(row.get("pct_chg", 0) or 0), 2),
        "main_net_inflow": round(_yi(row.get("main_net_inflow", 0)), 2),
        "inflow_5d": round(_yi(row.get("inflow_5d", 0)), 2),
        "inflow_10d": round(_yi(row.get("inflow_10d", 0)), 2),
        "diffusion": round(float(row.get("diffusion", 0) or 0), 2),
        "turning_point": bool(row.get("turning_point", False)),
        "top_leaders": str(row.get("top_leaders", "")),
        "children": _children_text(row.get("children", [])),
    }


def _build_leaders_for_sectors(sectors: list[str]) -> pd.DataFrame:
    frames = []
    for sector in sectors:
        try:
            leaders = build_universe(sectors=[sector], top_n=3)
        except Exception:
            continue
        if not leaders.empty:
            frames.append(leaders)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _hot_focus_histories(hot: pd.DataFrame, limit: int = 12) -> dict[str, pd.DataFrame]:
    if hot.empty or "code" not in hot.columns:
        return {}
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
    histories: dict[str, pd.DataFrame] = {}
    for _, row in hot.head(limit).iterrows():
        code = str(row.get("code", "") or "").zfill(6)
        if not code or code == "000000":
            continue
        symbol = _symbol_from_hot_row(row)
        try:
            hist = akshare_client.daily_hist(symbol, start, end)
        except Exception:
            hist = pd.DataFrame()
        if not hist.empty:
            histories[code] = hist
    return histories


def _symbol_from_hot_row(row: pd.Series) -> str:
    market_code = str(row.get("market_code", "") or "").upper()
    if market_code.startswith(("SH", "SZ")) and len(market_code) >= 8:
        return market_code[:2] + market_code[2:8].zfill(6)
    code = str(row.get("code", "") or "").zfill(6)
    return f"SH{code}" if code.startswith(("5", "6", "9")) else f"SZ{code}"


def _yi(value) -> float:
    if pd.isna(value):
        return 0.0
    return float(value) / 100_000_000


def _int_days(value) -> int:
    if pd.isna(value):
        return 0
    return int(round(float(value)))


def _children_text(value, limit: int = 6) -> str:
    if isinstance(value, (list, tuple, set)):
        return "、".join(str(item) for item in list(value)[:limit])
    return str(value or "")


if __name__ == "__main__":
    render_home()
