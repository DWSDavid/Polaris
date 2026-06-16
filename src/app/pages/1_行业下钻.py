from __future__ import annotations

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
    plotly_template,
    section,
    state_badge,
    status_line,
)
from src.compute.exit_signal import turning_point_score
from src.compute.fundamentals import sector_valuation_snapshot, valuation_guard
from src.compute.glossary import TERMS, explain_term
from src.compute.historical_analogy import build_analogy_samples, analogy_report
from src.compute.linkage_stats import leader_linkage_report
from src.compute.rotation_history import build_rotation_chain, summarize_flow_rotation
from src.compute.trend_v2 import streak_days
from src.data import em_client
from src.data.universe_v2 import build_universe, filter_noise, pick_leaders
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
    leaders = _build_leaders(sector, cons)
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
        leaders = data["leaders"]
        selected_panel = build_sector_panel_v2(
            industry_realtime=realtime[realtime["sector"] == sector],
            flow_5d=flow_5d[flow_5d["sector"] == sector],
            flow_10d=flow_10d[flow_10d["sector"] == sector],
            histories={sector: data["panel_hist"]},
            leaders=leaders,
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
    st.markdown(state_badge(str(row["state"])), unsafe_allow_html=True)
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

    trend_tab, flow_tab, leader_tab, advanced_tab, ai_tab = st.tabs(
        ["趋势", "资金 Track", "龙头列表", "v2.2 进阶", "AI 和解释"]
    )
    with trend_tab:
        _render_trend(sector, data["hist"], row)
    with flow_tab:
        _render_flow_track(sector, data["flow_hist"])
    with leader_tab:
        _render_leaders(data["leaders"])
    with advanced_tab:
        _render_v22_advanced(sector, row, data, flow_5d, flow_10d)
    with ai_tab:
        _render_ai_and_glossary(facts)


def _render_trend(sector: str, hist: pd.DataFrame, row: pd.Series) -> None:
    section("中期趋势", "看近90日位置和持续天数，避免只被当天涨跌牵着走。")
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
    plotly_template(fig)
    fig.update_layout(height=360)
    st.plotly_chart(fig, width="stretch")
    st.caption(
        f"trend_days={int(row['trend_days'])}，turning_point={bool(row['turning_point'])}。"
    )


def _render_flow_track(sector: str, flow_hist: pd.DataFrame) -> None:
    section("每日主力净流入", "连续性比单日脉冲更重要，重点看多周资金是否转正。")
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
    plotly_template(fig)
    fig.update_layout(height=360)
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
    section("龙头列表", "只看噪声过滤后的大公司和领先公司，避免小票噪声。")
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
                "展开展示系统拿到的实时快照；v2.2 进阶页已接入行业级历史类比与联动验证。"
            )


def _render_v22_advanced(
    sector: str,
    row: pd.Series,
    data: dict[str, pd.DataFrame],
    flow_5d: pd.DataFrame,
    flow_10d: pd.DataFrame,
) -> None:
    section("还能走多久", "用历史类比、资金接力、龙头联动和估值护栏交叉验证。")
    analogy = _build_current_analogy(row, data["panel_hist"])
    metric_grid(
        [
            ("相似样本", str(analogy["sample_count"])),
            ("中位还能走", f"{analogy['median_remaining_positive_days']:.0f} 天"),
            ("拐点分数", f"{_turn_score(row)['score']}/100"),
            ("拐点等级", _turn_score(row)["level"]),
        ]
    )
    st.write(analogy["summary"])

    section("资金接力")
    rotation_history = _rotation_history_from_periods(flow_5d, flow_10d)
    if rotation_history.empty:
        st.info("资金接力需要 5日/10日行业资金快照，当前暂不可用。")
    else:
        chain = build_rotation_chain(rotation_history, top_n=1)
        st.write(chain["summary"])
        rotation = summarize_flow_rotation(rotation_history, window=2)
        st.dataframe(_format_rotation_table(rotation.head(10)), width="stretch", height=280)

    section("龙头联动验证")
    linkage = _leader_linkage_proxy(data["hist"])
    st.write(linkage["summary"])
    st.caption("说明：当前使用行业指数历史作为代理；个股级龙头历史序列接入后，结论会更精确。")

    section("估值与拐点护栏")
    guard = _valuation_guard_for_sector(sector, data["cons"])
    score = _turn_score(row)
    if guard["level"] == "yellow":
        st.warning(guard["message"])
    elif guard["level"] == "unknown":
        st.info(guard["message"])
    else:
        st.success(guard["message"])
    if score["level"] == "high":
        st.error(score["message"])
    elif score["level"] == "medium":
        st.warning(score["message"])
    else:
        st.info(score["message"])


def _render_ai_and_glossary(facts: dict) -> None:
    section("AI 总结", "只喂系统算出的真实数值，方便解释但不替你下单。")
    st.dataframe(pd.DataFrame([facts]), width="stretch", height=120)
    st.write(_decision_summary(facts))

    section("名词解释")
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


def _build_leaders(sector: str, cons: pd.DataFrame) -> pd.DataFrame:
    try:
        leaders = build_universe(sectors=[sector], top_n=12)
    except Exception:
        leaders = pd.DataFrame()
    if not leaders.empty:
        return leaders
    return _leader_table(cons)


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


def _build_current_analogy(row: pd.Series, panel_hist: pd.DataFrame) -> dict:
    if panel_hist.empty:
        return analogy_report(pd.DataFrame(), str(row["state"]), int(row["trend_days"]))
    history = panel_hist.copy()
    if "close" not in history.columns or "pct_chg" not in history.columns:
        return analogy_report(pd.DataFrame(), str(row["state"]), int(row["trend_days"]))
    history["sector"] = str(row["sector"])
    history["state"] = history.apply(_historical_state, axis=1)
    trend_days = []
    pct = pd.to_numeric(history["pct_chg"], errors="coerce")
    for idx in range(len(history)):
        trend_days.append(streak_days(pct.iloc[: idx + 1]))
    history["trend_days"] = trend_days
    samples = build_analogy_samples(history, horizons=(3, 5), max_lookahead=10)
    return analogy_report(
        samples,
        state=str(row["state"]),
        trend_days=int(row.get("trend_days", 0) or 0),
        tolerance=2,
    )


def _historical_state(row: pd.Series) -> str:
    pct_chg = float(row.get("pct_chg", 0) or 0)
    flow = float(row.get("main_net_inflow", 0) or 0)
    if pct_chg > 0 and flow > 0:
        return "主升扩散"
    if pct_chg > 0 and flow <= 0:
        return "主力分化"
    if pct_chg <= 0 and flow > 0:
        return "低位修复"
    return "分歧退潮"


def _rotation_history_from_periods(flow_5d: pd.DataFrame, flow_10d: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for label, frame in [("10日累计", flow_10d), ("5日累计", flow_5d)]:
        if frame is None or frame.empty:
            continue
        for item in frame.to_dict("records"):
            rows.append(
                {
                    "trade_date": label,
                    "sector": item.get("sector"),
                    "main_net_inflow": item.get("main_net_inflow", 0),
                }
            )
    return pd.DataFrame(rows)


def _format_rotation_table(table: pd.DataFrame) -> pd.DataFrame:
    out = table.copy()
    flow_cols = [col for col in out.columns if col.startswith("flow_")]
    for col in list(dict.fromkeys([*flow_cols, "latest_flow", "flow_delta"])):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").map(
                lambda value: _yi_label(value, signed=True)
            )
    return out


def _leader_linkage_proxy(hist: pd.DataFrame) -> dict:
    if hist.empty or not {"trade_date", "pct_chg", "amount", "close"} <= set(hist.columns):
        return leader_linkage_report(pd.DataFrame(), pd.DataFrame())
    leader_daily = hist[["trade_date", "pct_chg", "amount"]].copy()
    amount = pd.to_numeric(leader_daily["amount"], errors="coerce")
    baseline = amount.rolling(20, min_periods=3).mean()
    leader_daily["volume_ratio"] = (amount / baseline).fillna(1.0)
    return leader_linkage_report(
        leader_daily[["trade_date", "pct_chg", "volume_ratio"]],
        hist[["trade_date", "close"]],
        horizons=[1, 3, 5],
    )


def _valuation_guard_for_sector(sector: str, cons: pd.DataFrame) -> dict:
    if cons.empty:
        return valuation_guard({"sector": sector, "median_pe_ttm": None, "valuation_coverage": 0})
    snapshot = sector_valuation_snapshot(cons)
    if snapshot.empty:
        return valuation_guard({"sector": sector, "median_pe_ttm": None, "valuation_coverage": 0})
    matched = snapshot[snapshot["sector"].astype(str) == str(sector)]
    target = matched.iloc[0] if not matched.empty else snapshot.iloc[0]
    return valuation_guard(target)


def _turn_score(row: pd.Series) -> dict:
    return turning_point_score(row, max_trend_days=7)


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
