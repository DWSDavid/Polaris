from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.app.ui import apply_theme, hero, metric_grid, page_intro, plotly_template, section, status_line
from src.compute.rotation_history import summarize_sector_track
from src.data import em_client
from src.data.sector_groups import (
    SECTOR_GROUP_DESCRIPTIONS,
    aggregate_timeline_to_groups,
    aggregate_to_groups,
    filter_actionable_groups,
)
from src.pipeline.rotation_timeline import (
    filter_rotation_groups,
    fetch_rotation_timeline,
    heatmap_flow_matrix,
    leader_changes,
    relative_flow_heatmap_matrix,
    select_rotation_sectors,
    weekly_rank,
)
from src.pipeline.sector_panel_v2 import build_sector_panel_v2


@st.cache_data(ttl=3600)
def get_rotation_timeline(days: int = 100, max_sectors: int = 32) -> pd.DataFrame:
    fine_timeline = fetch_rotation_timeline(days=days, max_sectors=max_sectors)
    return aggregate_timeline_to_groups(fine_timeline)


@st.cache_data(ttl=600)
def get_rotation_context_panel() -> dict[str, pd.DataFrame]:
    realtime = em_client.industry_realtime()
    flow_5d = em_client.industry_fund_flow("5日")
    flow_10d = em_client.industry_fund_flow("10日")
    fine_panel = build_sector_panel_v2(
        industry_realtime=realtime,
        flow_5d=flow_5d,
        flow_10d=flow_10d,
    )
    group_panel = filter_actionable_groups(aggregate_to_groups(fine_panel))
    return {"fine_panel": fine_panel, "group_panel": group_panel}


def render_page() -> None:
    st.set_page_config(page_title="Polaris 板块轮动历史", layout="wide")
    apply_theme()

    status_line("东财行业历史 · 约3个月窗口 · 小时级缓存")
    page_intro(
        "这页回答：过去3个月主线在大类板块之间怎么轮动。",
        "怎么用：带状图越靠上越强；热力图红色代表资金净流入、绿色代表净流出，先看接力顺序再去行业下钻。",
    )
    timeline = _safe_timeline()
    if timeline.empty:
        hero(
            "板块轮动历史",
            "当前没有可用的行业历史样本。先不要用空图判断轮动。",
            "3个月轮动 / 周排名 / 资金接力",
        )
        st.info("东财行业历史暂不可用，稍后重试。")
        return

    weekly_all = weekly_rank(timeline)
    weekly = filter_rotation_groups(weekly_all)
    changes = leader_changes(weekly)
    latest_week = _latest_week_label(weekly)
    latest_leader = _latest_leader(weekly)
    hero(
        "板块轮动历史",
        changes["summary"],
        "3个月轮动 / 周排名 / 资金接力",
    )
    metric_grid(
        [
            ("行业样本", str(timeline["sector"].nunique())),
            ("周数", str(weekly["week"].nunique())),
            ("当前领跑", latest_leader),
            ("最新周", latest_week),
        ]
    )

    bump_tab, heat_tab, leader_tab, explain_tab, stats_tab = st.tabs(
        ["排名带状图", "资金接力热力图", "龙头更替", "大类说明", "Stats"]
    )
    with bump_tab:
        _render_bump_chart(weekly)
    with heat_tab:
        _render_flow_heatmap(weekly)
    with leader_tab:
        _render_leader_changes(changes)
        _render_leader_context(changes)
    with explain_tab:
        _render_group_descriptions(weekly)
    with stats_tab:
        _render_stats(timeline)


def _safe_timeline() -> pd.DataFrame:
    try:
        return get_rotation_timeline()
    except Exception as exc:
        st.warning(f"轮动历史暂不可用：{exc}")
        return pd.DataFrame()


def _render_bump_chart(weekly: pd.DataFrame) -> None:
    section("排名带状图", "看过去3个月谁在连续领跑，谁刚开始抬头。")
    if weekly.empty:
        st.info("周排名样本不足。")
        return
    top_sectors = select_rotation_sectors(weekly, min_groups=6, max_groups=12)
    view = weekly[weekly["sector"].isin(top_sectors)].copy()
    fig = px.line(
        view,
        x="week_label",
        y="rank",
        color="sector",
        markers=True,
        hover_data=["week", "strength", "main_net_inflow"],
    )
    plotly_template(fig)
    fig.update_yaxes(autorange="reversed", dtick=1, title="周排名")
    week_order = _week_order(view)
    fig.update_xaxes(
        title="周区间（不是月份）",
        type="category",
        categoryorder="array",
        categoryarray=week_order,
    )
    fig.update_layout(height=460)
    st.plotly_chart(fig, width="stretch")
    st.caption("横轴是交易周区间，例如“06/15-06/21 · 第25周”，不是 2026 年 25 月。")


def _render_flow_heatmap(weekly: pd.DataFrame) -> None:
    section(
        "资金接力热力图",
        "默认看相对接力：红色代表本周在所有大类里相对更强，不等于绝对流入。",
    )
    if weekly.empty:
        st.info("资金接力样本不足。")
        return
    pivot, limit = relative_flow_heatmap_matrix(weekly, max_groups=18)
    if pivot.empty:
        st.info("资金接力样本不足。")
        return
    fig = px.imshow(
        pivot,
        aspect="auto",
        color_continuous_scale="RdYlGn_r",
        zmin=-limit if limit else None,
        zmax=limit if limit else None,
        labels=dict(x="周", y="行业", color="相对接力分"),
    )
    plotly_template(fig)
    fig.update_layout(height=560, coloraxis_colorbar=dict(title="相对接力"))
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "如果全市场资金都在流出，绝对净流入会一片绿；这里按每周横向排名重算，红色表示相对少流出或更有接力。"
    )
    with st.expander("查看绝对净流入矩阵"):
        absolute, _ = heatmap_flow_matrix(weekly, max_groups=18)
        st.dataframe(absolute, width="stretch", height=260)


def _render_leader_changes(changes: dict) -> None:
    section("龙头更替", "把每一段领跑行业串起来，看主线从哪里接力到哪里。")
    st.write(changes["summary"])
    segments = pd.DataFrame(changes.get("segments", []))
    if segments.empty:
        st.info("暂无领跑段落。")
        return
    st.dataframe(
        segments.rename(
            columns={
                "sector": "领跑行业",
                "start_week": "开始周",
                "end_week": "结束周",
                "duration_days": "持续天数",
                "strength": "段末强度",
            }
        ),
        width="stretch",
        height=260,
        column_config={"段末强度": st.column_config.NumberColumn(format="%.2f")},
    )


def _render_leader_context(changes: dict) -> None:
    section("领跑段落细节", "把每段领跑大类拆到细分行业和代表领涨股，判断是否真的可跟踪。")
    segments = pd.DataFrame(changes.get("segments", []))
    if segments.empty:
        return
    try:
        context = get_rotation_context_panel()
    except Exception as exc:
        st.info(f"实时细分快照暂不可用：{exc}")
        return
    detail = _leader_context_table(
        segments,
        context.get("group_panel", pd.DataFrame()),
        context.get("fine_panel", pd.DataFrame()),
    )
    if detail.empty:
        st.info("暂未匹配到实时细分板块。")
        return
    st.dataframe(detail, width="stretch", height=360, hide_index=True)


def _leader_context_table(
    segments: pd.DataFrame,
    group_panel: pd.DataFrame,
    fine_panel: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for segment in segments.to_dict("records"):
        sector = str(segment.get("sector", ""))
        group_hit = group_panel[group_panel["sector"].astype(str) == sector] if not group_panel.empty else pd.DataFrame()
        group_row = group_hit.iloc[0] if not group_hit.empty else pd.Series(dtype=object)
        fine = (
            fine_panel[fine_panel.get("group", pd.Series(dtype=str)).astype(str) == sector]
            if not fine_panel.empty and "group" in fine_panel.columns
            else pd.DataFrame()
        )
        rows.append(
            {
                "领跑大类": sector,
                "领跑周期": f"{segment.get('start_week')} → {segment.get('end_week')}",
                "持续天数": int(segment.get("duration_days", 0) or 0),
                "最近涨幅": _pct_label(group_row.get("pct_chg")),
                "10日资金": _yi_label(group_row.get("inflow_10d"), signed=True),
                "主导细分": group_row.get("trend_days_source", ""),
                "细分板块": _top_children(group_row.get("children"), fine),
                "代表领涨股": _leading_stock_text(fine),
            }
        )
    return pd.DataFrame(rows)


def _render_group_descriptions(weekly: pd.DataFrame) -> None:
    section("大类说明", "这些是东财细分行业上卷后的可读大类；“综合/其他”不参与主线领跑。")
    sectors = weekly["sector"].dropna().astype(str).drop_duplicates().tolist() if not weekly.empty else []
    rows = [
        {"大类": sector, "是什么意思": SECTOR_GROUP_DESCRIPTIONS.get(sector, "暂无解释")}
        for sector in sectors
    ]
    rows.append({"大类": "综合", "是什么意思": SECTOR_GROUP_DESCRIPTIONS["综合"]})
    st.dataframe(pd.DataFrame(rows), width="stretch", height=360, hide_index=True)


def _render_stats(timeline: pd.DataFrame) -> None:
    section("核心板块统计", "强势持续几段、平均多久、当前是延续还是转弱。")
    track = summarize_sector_track(_history_for_track(timeline), short_window=5, mid_window=15)
    if track.empty:
        st.info("统计样本不足。")
        return
    table = track.head(24).rename(
        columns={
            "sector": "行业",
            "fund_flow_5d": "5日资金",
            "fund_flow_15d": "15日资金",
            "positive_days_15d": "15日上涨天数",
            "current_positive_streak": "当前连涨",
            "latest_diffusion": "最新扩散",
            "track_label": "轮动位置",
        }
    )
    st.dataframe(
        table,
        width="stretch",
        height=460,
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


def _history_for_track(timeline: pd.DataFrame) -> pd.DataFrame:
    out = timeline.copy()
    out["trade_date"] = out["date"]
    out["avg_pct_chg"] = pd.to_numeric(out["pct_chg"], errors="coerce")
    out["fund_flow"] = pd.to_numeric(out["main_net_inflow"], errors="coerce").fillna(0)
    out["diffusion"] = (out["avg_pct_chg"] > 0).astype(float)
    return out[["trade_date", "sector", "avg_pct_chg", "fund_flow", "diffusion"]]


def _latest_leader(weekly: pd.DataFrame) -> str:
    if weekly.empty:
        return "-"
    latest = weekly[weekly["week"] == weekly["week"].max()].sort_values("rank")
    return str(latest.iloc[0]["sector"]) if not latest.empty else "-"


def _latest_week_label(weekly: pd.DataFrame) -> str:
    if weekly.empty:
        return "-"
    latest = weekly.sort_values("week_start" if "week_start" in weekly.columns else "week").iloc[-1]
    return str(latest.get("week_label") or latest.get("week") or "-")


def _week_order(weekly: pd.DataFrame) -> list[str]:
    if weekly.empty or "week_label" not in weekly.columns:
        return []
    if "week_start" in weekly.columns:
        ordered = weekly.sort_values("week_start")
    else:
        ordered = weekly.sort_values("week")
    return ordered["week_label"].dropna().astype(str).drop_duplicates().tolist()


def _top_children(children, fine: pd.DataFrame, limit: int = 6) -> str:
    if not fine.empty:
        ordered = fine.assign(_pct=pd.to_numeric(fine.get("pct_chg"), errors="coerce")).sort_values(
            "_pct", ascending=False
        )
        names = [
            f"{row.sector}({_pct_label(row.pct_chg)})"
            for row in ordered.head(limit).itertuples()
        ]
        return "、".join(names)
    if isinstance(children, (list, tuple, set)):
        return "、".join(str(item) for item in list(children)[:limit])
    return str(children or "")


def _leading_stock_text(fine: pd.DataFrame, limit: int = 6) -> str:
    if fine.empty or "leading_stock" not in fine.columns:
        return ""
    ordered = fine.assign(
        _pct=pd.to_numeric(fine.get("leading_stock_pct_chg"), errors="coerce")
    ).sort_values("_pct", ascending=False, na_position="last")
    names = []
    for row in ordered.head(limit).itertuples():
        stock = str(getattr(row, "leading_stock", "") or "")
        if not stock:
            continue
        names.append(f"{stock}({_pct_label(getattr(row, 'leading_stock_pct_chg', None))})")
    return "、".join(names)


def _yi_label(value, signed: bool = False) -> str:
    try:
        amount = 0.0 if pd.isna(value) else float(value) / 100_000_000
    except (TypeError, ValueError):
        amount = 0.0
    prefix = "+" if signed and amount > 0 else ""
    return f"{prefix}{amount:.1f}亿"


def _pct_label(value) -> str:
    try:
        if pd.isna(value):
            return "-"
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "-"


if __name__ == "__main__":
    render_page()
