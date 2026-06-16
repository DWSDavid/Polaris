from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from src.ai.summarize import summarize_sector
from src.app.ui import apply_theme, hero, metric_grid, note, status_line
from src.compute.glossary import TERMS, explain_term
from src.data import em_client
from src.data.universe_v2 import filter_noise, pick_leaders
from src.pipeline.sector_panel_v2 import build_sector_panel_v2


@st.cache_data(ttl=600)
def get_realtime_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        em_client.industry_realtime(),
        em_client.industry_fund_flow("5日"),
        em_client.industry_fund_flow("10日"),
    )


@st.cache_data(ttl=600)
def get_sector_drilldown(sector: str) -> dict[str, pd.DataFrame]:
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
    hist = _safe_frame(em_client.industry_hist, sector, start, end)
    flow_hist = _safe_frame(em_client.industry_fund_flow_hist, sector)
    cons = _safe_frame(em_client.industry_cons, sector)
    leaders = _leader_table(cons)
    panel_hist = _merge_history_with_flow(hist, flow_hist)
    return {
        "hist": hist,
        "flow_hist": flow_hist,
        "cons": cons,
        "leaders": leaders,
        "panel_hist": panel_hist,
    }


def render_page() -> None:
    st.set_page_config(page_title="Polaris 行业下钻", layout="wide")
    apply_theme()

    try:
        realtime, flow_5d, flow_10d = get_realtime_inputs()
    except Exception as exc:
        status_line("东财实时未接入，行业下钻暂不可用")
        st.error(f"东财接口异常：{exc}")
        return

    if realtime.empty:
        status_line("东财实时未接入，行业下钻暂不可用")
        return

    sectors = (
        realtime.sort_values(["pct_chg", "main_net_inflow"], ascending=False)["sector"]
        .dropna()
        .astype(str)
        .tolist()
    )
    default_index = sectors.index("银行") if "银行" in sectors else 0
    sector = st.selectbox("选择行业", sectors, index=default_index)

    try:
        data = get_sector_drilldown(sector)
        selected_panel = build_sector_panel_v2(
            industry_realtime=realtime[realtime["sector"] == sector],
            flow_5d=flow_5d[flow_5d["sector"] == sector],
            flow_10d=flow_10d[flow_10d["sector"] == sector],
            histories={sector: data["panel_hist"]},
            leaders=data["leaders"],
        )
    except Exception as exc:
        status_line("行业下钻加载失败")
        st.error(f"{sector} 数据暂不可用：{exc}")
        return

    if selected_panel.empty:
        status_line("行业下钻加载失败")
        st.warning(f"{sector} 暂无可用数据")
        return

    row = selected_panel.iloc[0]
    facts = _facts(row)
    status_line(
        f"东财实时已接入 · {sector} · 10分钟刷新 · AI 只读取本页真实数值"
    )
    hero(
        f"{sector}：{row['state']}",
        _decision_summary(facts),
        "行业下钻 / 中期趋势 / 资金 track / 龙头展开",
    )
    metric_grid(
        [
            ("趋势已持续", f"{int(row['trend_days'])} 天"),
            ("今日主力", _yi_label(row["main_net_inflow"], signed=True)),
            ("10日主力", _yi_label(row["inflow_10d"], signed=True)),
            ("扩散度", _ratio_label(row["diffusion"])),
        ]
    )
    if bool(row.get("turning_point", False)):
        note("拐点提示：价格或资金出现转弱，先降低追高假设，等下一次扩散确认。")

    trend_tab, flow_tab, leader_tab, ai_tab = st.tabs(
        ["趋势", "资金 Track", "龙头列表", "AI 和解释"]
    )
    with trend_tab:
        _render_trend(sector, data["hist"], row)
    with flow_tab:
        _render_flow_track(sector, data["flow_hist"])
    with leader_tab:
        _render_leaders(data["leaders"])
    with ai_tab:
        _render_ai_and_glossary(facts)


def _render_trend(sector: str, hist: pd.DataFrame, row: pd.Series) -> None:
    st.subheader("中期趋势")
    if hist.empty:
        st.info("行业历史行情暂不可用。")
        return
    plot = hist.tail(90).copy()
    plot["trade_date"] = pd.to_datetime(plot["trade_date"], errors="coerce")
    fig = px.line(
        plot,
        x="trade_date",
        y="close",
        title=f"{sector} 近90日收盘趋势",
        markers=False,
    )
    fig.update_layout(height=360, margin=dict(t=42, l=0, r=0, b=0))
    st.plotly_chart(fig, width="stretch")
    st.caption(
        f"trend_days={int(row['trend_days'])}，turning_point={bool(row['turning_point'])}。"
    )


def _render_flow_track(sector: str, flow_hist: pd.DataFrame) -> None:
    st.subheader("每日主力净流入")
    if flow_hist.empty:
        st.info("行业资金流历史暂不可用。")
        return
    plot = flow_hist.tail(60).copy()
    plot["trade_date"] = pd.to_datetime(plot["trade_date"], errors="coerce")
    plot["main_net_inflow_yi"] = _num(plot["main_net_inflow"]) / 100_000_000
    fig = px.bar(
        plot,
        x="trade_date",
        y="main_net_inflow_yi",
        color="main_net_inflow_yi",
        color_continuous_scale="RdYlGn",
        title=f"{sector} 近60个交易日主力净流入(亿)",
    )
    fig.update_layout(height=360, margin=dict(t=42, l=0, r=0, b=0))
    st.plotly_chart(fig, width="stretch")

    latest = plot.tail(10)[
        [
            "trade_date",
            "main_net_inflow",
            "main_net_inflow_pct",
            "super_large_inflow",
            "large_inflow",
        ]
    ].copy()
    latest["main_net_inflow"] = latest["main_net_inflow"].map(
        lambda value: _yi_label(value, signed=True)
    )
    latest["super_large_inflow"] = latest["super_large_inflow"].map(
        lambda value: _yi_label(value, signed=True)
    )
    latest["large_inflow"] = latest["large_inflow"].map(
        lambda value: _yi_label(value, signed=True)
    )
    st.dataframe(latest, width="stretch", height=280)


def _render_leaders(leaders: pd.DataFrame) -> None:
    st.subheader("龙头列表")
    if leaders.empty:
        st.info("噪声过滤后暂未找到满足市值和成交额门槛的成分股。")
        return

    table = leaders.head(20).copy()
    table["成交额(亿)"] = table["amount"].map(_yi)
    table["总市值(亿)"] = table["total_mv"].map(_yi)
    table = table[
        [
            "rank",
            "code",
            "name",
            "pct_chg",
            "成交额(亿)",
            "总市值(亿)",
            "turnover",
            "pe_ttm",
            "pb",
        ]
    ].rename(
        columns={
            "rank": "排名",
            "code": "代码",
            "name": "名称",
            "pct_chg": "涨跌幅",
            "turnover": "换手率",
            "pe_ttm": "PE(动)",
            "pb": "PB",
        }
    )
    st.dataframe(table, width="stretch", height=380)

    for item in leaders.head(8).itertuples():
        with st.expander(f"{int(item.rank)} · {item.name} · {item.code}"):
            metric_grid(
                [
                    ("涨跌幅", _pct_label(item.pct_chg)),
                    ("成交额", _yi_label(item.amount)),
                    ("总市值", _yi_label(item.total_mv)),
                    ("换手率", _pct_label(item.turnover)),
                ]
            )
            st.write(
                "展开只展示系统拿到的实时快照；个股历史联动会在 v2.1/v2.2 继续接上。"
            )


def _render_ai_and_glossary(facts: dict) -> None:
    st.subheader("AI 总结")
    st.dataframe(pd.DataFrame([facts]), width="stretch", height=120)
    st.write(_decision_summary(facts))

    st.subheader("名词解释")
    for term in ["冷启动", "主升扩散", "龙头孤立", "主力分化", "拐点"]:
        with st.expander(term):
            st.write(explain_term(term))
    with st.expander("全部术语"):
        st.dataframe(
            pd.DataFrame(
                [{"term": term, "explain": explain_term(term)} for term in TERMS]
            ),
            width="stretch",
            height=260,
        )


def _leader_table(cons: pd.DataFrame) -> pd.DataFrame:
    if cons.empty:
        return cons
    filtered = filter_noise(cons, min_mv=2_000_000_000, min_amount=100_000_000)
    if filtered.empty:
        filtered = cons.copy()
    return pick_leaders(filtered, top_n=12)


def _safe_frame(fn, *args) -> pd.DataFrame:
    try:
        return fn(*args)
    except Exception:
        return pd.DataFrame()


def _merge_history_with_flow(hist: pd.DataFrame, flow_hist: pd.DataFrame) -> pd.DataFrame:
    if hist.empty:
        return hist
    out = hist.copy()
    if not flow_hist.empty:
        out = out.merge(
            flow_hist[["trade_date", "main_net_inflow"]],
            on="trade_date",
            how="left",
        )
    if "main_net_inflow" not in out.columns:
        out["main_net_inflow"] = 0.0
    return out


def _decision_summary(facts: dict) -> str:
    text = summarize_sector(facts)
    if "API Key" in text:
        return _local_summary(facts)
    return text


def _local_summary(facts: dict) -> str:
    warning = "，出现拐点预警" if facts["turning_point"] else ""
    return (
        f"{facts['sector']}当前是{facts['state']}，趋势已持续{facts['trend_days']}天，"
        f"10日主力净流入{facts['inflow_10d']:+.1f}亿，今日主力"
        f"{facts['main_net_inflow']:+.1f}亿，扩散度{facts['diffusion']:.0%}"
        f"{warning}。先看龙头是否继续带动中军，不把 AI 文案当买卖指令。"
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
    }


def _num(values) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").fillna(0.0)


def _yi(value) -> float:
    if pd.isna(value):
        return 0.0
    return float(value) / 100_000_000


def _yi_label(value, signed: bool = False) -> str:
    amount = _yi(value)
    prefix = "+" if signed and amount > 0 else ""
    return f"{prefix}{amount:.2f} 亿"


def _pct_label(value) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value):+.2f}%"


def _ratio_label(value) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value):.0%}"


if __name__ == "__main__":
    render_page()
