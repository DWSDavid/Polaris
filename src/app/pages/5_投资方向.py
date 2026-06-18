from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from src.ai.advise import advise
from src.app.ui import apply_theme, hero, metric_grid, page_intro, plotly_template, section, state_badge, status_line
from src.compute.cycle import box_range, cum_inflow, midterm_trend, position_in_box
from src.compute.divergence import structural_hedge_pairs
from src.compute.ignition import ignition_flag, ignition_score
from src.compute.mainline import mainline_score
from src.compute.synthesis import direction_score, rank_directions
from src.compute.trust import TRUST_DISCLAIMER, trust_badge, with_disclaimer
from src.data import em_client, em_context
from src.data.sector_groups import (
    aggregate_timeline_to_groups,
    aggregate_to_groups,
    filter_actionable_groups,
)
from src.pipeline.direction_history import (
    build_direction_snapshot,
    load_direction_history,
    save_direction_snapshot,
)
from src.pipeline.rotation_timeline import fetch_rotation_timeline
from src.pipeline.sector_panel_v2 import build_sector_panel_v2

DEFAULT_HOLDING = {"code": "601688", "name": "华泰证券", "sector": "证券"}


@st.cache_data(ttl=600)
def get_direction_payload() -> dict:
    as_of = datetime.now().strftime("%Y-%m-%d %H:%M")
    realtime = _safe_frame(em_client.industry_realtime)
    flow_5d = _safe_frame(em_client.industry_fund_flow, "5日")
    flow_10d = _safe_frame(em_client.industry_fund_flow, "10日")
    timeline = fetch_rotation_timeline(days=90, max_sectors=24)
    group_timeline = aggregate_timeline_to_groups(timeline)
    histories = _histories_from_timeline(timeline)
    fine_panel = build_sector_panel_v2(
        industry_realtime=realtime,
        flow_5d=flow_5d,
        flow_10d=flow_10d,
        histories=histories,
    )
    panel = filter_actionable_groups(aggregate_to_groups(fine_panel))
    panel = mainline_score(panel).sort_values(
        ["mainline_score", "strength_rank"], ascending=False
    )
    context = _load_context(DEFAULT_HOLDING["code"])
    candidates = _build_direction_facts(panel, group_timeline, context)
    ranked = _attach_trust(rank_directions(candidates), as_of)
    snapshot = build_direction_snapshot(ranked, as_of=as_of)
    try:
        save_direction_snapshot(snapshot)
    except OSError:
        pass
    return {
        "panel": panel,
        "fine_panel": fine_panel,
        "timeline": timeline,
        "group_timeline": group_timeline,
        "context": context,
        "ranked": ranked,
        "history": load_direction_history(limit=20),
        "as_of": as_of,
    }


def render_page() -> None:
    st.set_page_config(page_title="Polaris 投资方向", layout="wide")
    apply_theme()
    page_intro(
        "这页回答：当前更值得观察的大类方向，以及哪些方向应回避。",
        "怎么用：先看Top方向和回避方向，再看细分板块、20日资金、箱体位置和对冲惩罚；AI 只解释已算出的事实。",
    )

    try:
        payload = get_direction_payload()
        load_error = None
    except Exception as exc:
        payload = {"panel": pd.DataFrame(), "timeline": pd.DataFrame(), "context": {}, "ranked": []}
        load_error = exc

    ranked = payload["ranked"]
    if not ranked:
        status_line("方向综合暂不可用")
        if load_error:
            st.error(f"方向综合失败：{load_error}")
        hero(
            "投资方向",
            "当前缺少可用行业数据。不要把空结论当作市场判断。",
            "综合方向 / AI 解释 / 证据就地展示",
        )
        return

    avoid = [item["sector"] for item in ranked if item["score"] < 0][:3]
    ai_facts = {
        "ranked_directions": ranked[:6],
        "avoid_directions": avoid,
        "market_context": _market_context_summary(payload["context"]),
        "holdings": [
            {
                "name": DEFAULT_HOLDING["name"],
                "sector": DEFAULT_HOLDING["sector"],
                "state": _state_for_holding(payload.get("fine_panel", payload["panel"])),
            }
        ],
        "today_watch": _today_watch(ranked),
        "trust_note": ranked[0].get("trust_summary", "") if ranked else "",
    }
    ai_text = _safe_advise(ai_facts)

    top = ranked[0]
    status_line("东财行业 + AKShare context · 10分钟缓存 · 人最后决定")
    st.markdown(state_badge(str(top.get("state", "未知"))), unsafe_allow_html=True)
    hero(
        f"投资方向：{top['sector']}",
        ai_text,
        "中长期方向 / 资金接力 / 龙虎榜与新闻佐证",
    )
    metric_grid(
        [
            ("Top 分数", f"{float(top['score']):.2f}"),
            ("20日资金", f"{_yi(top.get('cum_inflow_20d')):+.1f} 亿"),
            ("趋势持续", f"{int(top.get('trend_days', 0) or 0)} 天"),
            ("启动", "是" if bool(top.get("ignition_flag")) else "否"),
        ]
    )

    direction_tab, evidence_tab, history_tab, glossary_tab = st.tabs(
        ["方向排序", "佐证", "历史记录", "名词解释"]
    )
    with direction_tab:
        _render_direction_overview(ranked)
        _render_direction_cards(ranked[:6])
    with evidence_tab:
        _render_context(payload["context"])
    with history_tab:
        _render_direction_history(payload.get("history", []))
    with glossary_tab:
        _render_glossary()


def _render_direction_overview(ranked: list[dict]) -> None:
    section("综合方向排序", "只把系统已经算出的趋势、资金、启动、估值和对冲信号串起来。")
    chart = pd.DataFrame(ranked[:10])
    if chart.empty:
        return
    fig = px.bar(
        chart.sort_values("score"),
        x="score",
        y="sector",
        orientation="h",
        color="score",
        color_continuous_scale="RdYlGn",
        hover_data=["state", "trend_days", "cum_inflow_20d", "ignition_flag"],
    )
    plotly_template(fig)
    fig.update_layout(height=420, coloraxis_showscale=False)
    st.plotly_chart(fig, width="stretch")


def _render_direction_cards(items: list[dict]) -> None:
    for index, item in enumerate(items, start=1):
        with st.container(border=True):
            cols = st.columns([1.2, 0.8, 0.8, 0.8])
            cols[0].markdown(f"#### {index}. {item['sector']}")
            cols[1].metric("综合分", f"{direction_score(item):.2f}")
            cols[2].metric("20日资金", f"{_yi(item.get('cum_inflow_20d')):+.1f} 亿")
            cols[3].metric("箱体位置", f"{float(item.get('position_in_box', 0) or 0):.0%}")
            st.markdown(state_badge(str(item.get("state", "未知"))), unsafe_allow_html=True)
            st.caption(f"凭据强度：{item.get('trust_summary', '暂无可信度标签')}")
            st.write(" / ".join(str(reason) for reason in item.get("reasons", [])))
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "中期趋势": _trend_label(item.get("midterm_trend")),
                            "启动迹象": bool(item.get("ignition_flag")),
                            "启动分": item.get("ignition_score"),
                            "扩散": item.get("diffusion"),
                            "龙头": item.get("top_leaders"),
                            "细分板块": _children_text(item.get("children")),
                            "凭据强度": item.get("trust_summary"),
                            "对冲惩罚": item.get("hedge_penalty"),
                            "拐点": bool(item.get("turning_point")),
                        }
                    ]
                ),
                width="stretch",
                height=82,
                hide_index=True,
            )


def _render_context(context: dict) -> None:
    section("佐证就地展示", "北向、龙虎榜、研报、新闻都放在这里，避免各看各的。")
    northbound = context.get("northbound", pd.DataFrame())
    dragon = context.get("dragon_tiger", pd.DataFrame())
    research = context.get("research", pd.DataFrame())
    news = context.get("news", pd.DataFrame())

    cols = st.columns(2)
    with cols[0]:
        st.subheader("北向资金")
        if northbound.empty:
            st.info("北向资金暂不可用。")
        else:
            view = northbound.head(8).copy()
            st.dataframe(view, width="stretch", height=260)
    with cols[1]:
        st.subheader("龙虎榜")
        if dragon.empty:
            st.info("龙虎榜暂不可用。")
        else:
            columns = [col for col in ["trade_date", "code", "name", "pct_chg", "net_buy", "reason"] if col in dragon.columns]
            st.dataframe(dragon[columns].head(12), width="stretch", height=260)

    cols = st.columns(2)
    with cols[0]:
        st.subheader(f"{DEFAULT_HOLDING['name']}研报")
        if research.empty:
            st.info("研报暂不可用。")
        else:
            columns = [col for col in ["date", "title", "rating", "org", "industry"] if col in research.columns]
            st.dataframe(research[columns].head(8), width="stretch", height=260)
    with cols[1]:
        st.subheader(f"{DEFAULT_HOLDING['name']}新闻")
        if news.empty:
            st.info("新闻暂不可用。")
        else:
            columns = [col for col in ["publish_time", "title", "source"] if col in news.columns]
            st.dataframe(news[columns].head(8), width="stretch", height=260)


def _render_direction_history(history: list[dict]) -> None:
    section("历史记录", "每天保留一份 Top 方向快照，用来观察建议是否连续，而不是每天追着换仓。")
    if not history:
        st.info("还没有历史快照。打开本页后会自动保存当天方向记录。")
        return
    rows = []
    for snapshot in history:
        top = snapshot.get("top_directions") or []
        rows.append(
            {
                "日期": snapshot.get("date"),
                "记录时间": snapshot.get("as_of"),
                "Top方向": "、".join(item.get("sector", "") for item in top[:3]),
                "Top理由": "；".join(
                    "、".join(item.get("reasons", [])[:2]) for item in top[:3]
                ),
                "摘要": snapshot.get("summary"),
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", height=420, hide_index=True)


def _render_glossary() -> None:
    section("名词解释", "这些解释只帮助读页面，不替代你自己的判断。")
    entries = {
        "冷启动": "刚从弱势或箱体里冒头，确认度还不高，适合观察是否扩散。",
        "主升扩散": "板块涨幅、资金和上涨家数一起走强，不只是一两只龙头在拉。",
        "资金接力": "资金从一个方向轮到另一个方向，连续多日或多周更有意义。",
        "箱体位置": "当前价格在近一段区间里的相对位置，越高越接近压力区。",
        "对冲惩罚": "和当前持仓方向可能相互抵消时降低分数，比如金融和成长股跷跷板。",
    }
    for name, body in entries.items():
        with st.expander(name):
            st.write(body)


def _build_direction_facts(panel: pd.DataFrame, timeline: pd.DataFrame, context: dict) -> list[dict]:
    candidates = []
    if panel.empty:
        return candidates
    northbound_pos = _northbound_positive(context.get("northbound", pd.DataFrame()))
    dragon = context.get("dragon_tiger", pd.DataFrame())
    top_panel = panel.head(28).copy()
    for row in top_panel.to_dict("records"):
        sector = str(row.get("sector", ""))
        history = timeline[timeline["sector"] == sector].sort_values("date") if not timeline.empty else pd.DataFrame()
        close = _pseudo_close(history.get("pct_chg", pd.Series(dtype=float)))
        if close.empty:
            close = pd.Series([100.0])
        high, low = box_range(close, window=60)
        position = position_in_box(float(close.iloc[-1]), high, low)
        midterm = midterm_trend(close, short=10, long=min(30, max(10, len(close))))
        if midterm == 0:
            midterm = int(row.get("trend20", 0) or 0)
        inflow_20d = cum_inflow(history.get("main_net_inflow", pd.Series(dtype=float)), window=20)
        if inflow_20d == 0:
            inflow_20d = float(row.get("main_net_inflow", 0) or 0) + float(row.get("inflow_10d", 0) or 0)
        feats = {
            "position_in_box": position,
            "cum_inflow_20d": inflow_20d,
            "volume_amp": row.get("volume_amp", 1.0),
            "diffusion": row.get("diffusion", 0.0),
            "midterm_trend": midterm,
            "was_ranging": position < 0.9,
        }
        ign_score = ignition_score(feats)
        leaders = str(row.get("top_leaders", ""))
        candidates.append(
            {
                "sector": sector,
                "state": str(row.get("state", "未知")),
                "top_leaders": leaders,
                "midterm_trend": midterm,
                "cum_inflow_20d": inflow_20d,
                "trend_days": int(row.get("trend_days", 0) or 0),
                "ignition_flag": ignition_flag(feats, threshold=0.55),
                "ignition_score": ign_score,
                "northbound_pos": northbound_pos,
                "lhb_active": _dragon_tiger_active(leaders, dragon),
                "turning_point": bool(row.get("turning_point", False)),
                "valuation_pct": None,
                "hedge_penalty": _hedge_penalty(sector),
                "position_in_box": position,
                "diffusion": float(row.get("diffusion", 0) or 0),
                "mainline_score": float(row.get("mainline_score", 0) or 0),
                "pct_chg": float(row.get("pct_chg", 0) or 0),
                "children": row.get("children", []),
                "stock_count": float(row.get("stock_count", 0) or 0),
            }
        )
    return candidates


def _load_context(symbol: str) -> dict:
    return {
        "northbound": _safe_frame(em_context.northbound_flow),
        "dragon_tiger": _safe_frame(em_context.dragon_tiger),
        "research": _safe_frame(em_context.research_reports, symbol),
        "news": _safe_frame(em_context.stock_news, symbol),
    }


def _market_context_summary(context: dict) -> dict:
    northbound = context.get("northbound", pd.DataFrame())
    dragon = context.get("dragon_tiger", pd.DataFrame())
    research = context.get("research", pd.DataFrame())
    news = context.get("news", pd.DataFrame())
    return {
        "northbound_rows": int(len(northbound)),
        "northbound_positive": _northbound_positive(northbound),
        "dragon_tiger_rows": int(len(dragon)),
        "research_titles": _head_values(research, "title", 3),
        "news_titles": _head_values(news, "title", 3),
    }


def _attach_trust(items: list[dict], as_of: str) -> list[dict]:
    trusted = []
    for item in items:
        badge = trust_badge(item, as_of=as_of)
        trusted.append({**item, "trust": badge, "trust_summary": badge["summary"]})
    return trusted


def _histories_from_timeline(timeline: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if timeline.empty:
        return {}
    out = {}
    for sector, group in timeline.groupby("sector"):
        hist = group.rename(columns={"date": "trade_date"}).copy()
        out[str(sector)] = hist
    return out


def _safe_frame(func, *args) -> pd.DataFrame:
    try:
        return func(*args)
    except Exception:
        return pd.DataFrame()


def _pseudo_close(pct_chg: pd.Series) -> pd.Series:
    pct = pd.to_numeric(pct_chg, errors="coerce").fillna(0) / 100
    if pct.empty:
        return pd.Series(dtype=float)
    return (1 + pct).cumprod() * 100


def _northbound_positive(northbound: pd.DataFrame) -> bool:
    if northbound.empty:
        return False
    for column in ["fund_net_inflow", "net_buy_amount"]:
        if column in northbound.columns:
            values = pd.to_numeric(northbound[column], errors="coerce").dropna()
            if not values.empty:
                return float(values.tail(3).sum()) >= 0
    return False


def _dragon_tiger_active(leaders: str, dragon: pd.DataFrame) -> bool:
    if dragon.empty or not leaders:
        return False
    names = dragon.get("name", pd.Series(dtype=str)).dropna().astype(str).tolist()
    return any(name and name in leaders for name in names)


def _hedge_penalty(sector: str) -> float:
    pairs = structural_hedge_pairs([DEFAULT_HOLDING["sector"], sector])
    return 0.35 if pairs else 0.0


def _state_for_holding(panel: pd.DataFrame) -> str:
    if panel.empty:
        return "未知"
    hit = panel[panel["sector"].astype(str).str.contains(DEFAULT_HOLDING["sector"], na=False)]
    return str(hit.iloc[0].get("state", "未知")) if not hit.empty else "未知"


def _today_watch(ranked: list[dict]) -> str:
    top = ranked[0]
    return (
        f"观察{top['sector']}资金是否继续为正、扩散是否保持；"
        f"若华泰证券所在证券方向与Top方向形成对冲，控制持仓集中度。"
    )


def _local_ai_fallback(facts: dict) -> str:
    ranked = facts.get("ranked_directions") or []
    if not ranked:
        return "暂无可用方向排序。人最后决定，不自动下单。"
    top = ranked[0]
    avoid = "、".join(facts.get("avoid_directions") or []) or "暂无"
    return (
        f"1. 周期判断：{top['sector']}分数最高，理由是{'、'.join(top.get('reasons', [])[:3])}。"
        f"2. 资金与分化：先看20日资金和扩散能否延续。"
        f"3. 龙头联动：盯{top.get('top_leaders', '龙头')}是否继续带动。"
        f"4. 对冲与担保比：当前样例持仓为华泰证券，回避方向为{avoid}。"
        f"5. 今日观察：只做决策辅助，人最后决定。"
    )


def _safe_advise(facts: dict) -> str:
    try:
        text = advise(facts, timeout=8)
    except Exception:
        return with_disclaimer(_local_ai_fallback(facts))
    if text.startswith("未配置 AI API Key"):
        return with_disclaimer(_local_ai_fallback(facts))
    return with_disclaimer(text or _local_ai_fallback(facts))


def _head_values(frame: pd.DataFrame, column: str, limit: int) -> list[str]:
    if frame.empty or column not in frame.columns:
        return []
    return frame[column].dropna().astype(str).head(limit).tolist()


def _trend_label(value) -> str:
    number = int(value or 0)
    if number > 0:
        return "向上"
    if number < 0:
        return "向下"
    return "震荡"


def _yi(value) -> float:
    if value is None or pd.isna(value):
        return 0.0
    return float(value) / 100_000_000


def _children_text(value, limit: int = 6) -> str:
    if isinstance(value, (list, tuple, set)):
        return "、".join(str(item) for item in list(value)[:limit])
    return str(value or "")


if __name__ == "__main__":
    render_page()
