from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.app.ui import apply_theme, hero, metric_grid, plotly_template, section, status_line
from src.compute.rotation_history import summarize_sector_track
from src.data.sector_groups import aggregate_timeline_to_groups
from src.pipeline.rotation_timeline import (
    fetch_rotation_timeline,
    leader_changes,
    weekly_rank,
)


@st.cache_data(ttl=3600)
def get_rotation_timeline(days: int = 100, max_sectors: int = 32) -> pd.DataFrame:
    fine_timeline = fetch_rotation_timeline(days=days, max_sectors=max_sectors)
    return aggregate_timeline_to_groups(fine_timeline)


def render_page() -> None:
    st.set_page_config(page_title="Polaris 板块轮动历史", layout="wide")
    apply_theme()

    status_line("东财行业历史 · 约3个月窗口 · 小时级缓存")
    timeline = _safe_timeline()
    if timeline.empty:
        hero(
            "板块轮动历史",
            "当前没有可用的行业历史样本。先不要用空图判断轮动。",
            "3个月轮动 / 周排名 / 资金接力",
        )
        st.info("东财行业历史暂不可用，稍后重试。")
        return

    weekly = weekly_rank(timeline)
    changes = leader_changes(weekly)
    latest_week = str(weekly["week"].max())
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

    bump_tab, heat_tab, leader_tab, stats_tab = st.tabs(
        ["排名带状图", "资金接力热力图", "龙头更替", "Stats"]
    )
    with bump_tab:
        _render_bump_chart(weekly)
    with heat_tab:
        _render_flow_heatmap(weekly)
    with leader_tab:
        _render_leader_changes(changes)
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
    top_sectors = (
        weekly.groupby("sector")["rank"].min().sort_values().head(14).index.tolist()
    )
    view = weekly[weekly["sector"].isin(top_sectors)].copy()
    fig = px.line(
        view,
        x="week",
        y="rank",
        color="sector",
        markers=True,
        hover_data=["strength", "main_net_inflow"],
    )
    plotly_template(fig)
    fig.update_yaxes(autorange="reversed", dtick=1, title="周排名")
    fig.update_xaxes(title="周")
    fig.update_layout(height=460)
    st.plotly_chart(fig, width="stretch")


def _render_flow_heatmap(weekly: pd.DataFrame) -> None:
    section("资金接力热力图", "红色为周度净流入更强，绿色为转弱流出。")
    if weekly.empty:
        st.info("资金接力样本不足。")
        return
    top_sectors = (
        weekly.groupby("sector")["main_net_inflow"].sum().abs().sort_values(ascending=False).head(18).index
    )
    view = weekly[weekly["sector"].isin(top_sectors)].copy()
    view["flow_yi"] = pd.to_numeric(view["main_net_inflow"], errors="coerce") / 100_000_000
    pivot = view.pivot_table(
        index="sector",
        columns="week",
        values="flow_yi",
        aggfunc="sum",
        fill_value=0,
    )
    fig = px.imshow(
        pivot,
        aspect="auto",
        color_continuous_scale="RdYlGn_r",
        labels=dict(x="周", y="行业", color="净流入(亿)"),
    )
    plotly_template(fig)
    fig.update_layout(height=560)
    st.plotly_chart(fig, width="stretch")


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
                "strength": "段末强度",
            }
        ),
        width="stretch",
        height=260,
        column_config={"段末强度": st.column_config.NumberColumn(format="%.2f")},
    )


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


if __name__ == "__main__":
    render_page()
