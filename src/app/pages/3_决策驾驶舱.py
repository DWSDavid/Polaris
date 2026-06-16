from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from src.ai.advise import advise
from src.app.ui import apply_theme, hero, metric_grid, note, status_line
from src.compute.exit_signal import exit_flag
from src.compute.portfolio_exposure import match_sector_name
from src.data import account, basket, em_client
from src.pipeline.sector_panel_v2 import build_sector_panel_v2


@st.cache_data(ttl=600)
def get_decision_panel() -> pd.DataFrame:
    realtime = em_client.industry_realtime()
    flow_5d = em_client.industry_fund_flow("5日")
    flow_10d = em_client.industry_fund_flow("10日")
    return build_sector_panel_v2(
        industry_realtime=realtime,
        flow_5d=flow_5d,
        flow_10d=flow_10d,
    )


def render_page() -> None:
    st.set_page_config(page_title="Polaris 决策驾驶舱", layout="wide")
    apply_theme()

    try:
        panel = get_decision_panel()
        load_error = None
    except Exception as exc:
        panel = pd.DataFrame()
        load_error = exc

    if panel.empty:
        status_line("东财行业面板暂不可用，候选篮子无法计算。")
        if load_error:
            st.error(f"东财接口异常：{load_error}")
        return

    acct = account.load()
    stored = basket.load_basket()
    sectors = panel["sector"].dropna().astype(str).tolist()
    defaults = [
        matched
        for matched in (
            match_sector_name(item, sectors) for item in (stored or ["证券", "电子"])
        )
        if matched in sectors
    ]

    hero(
        "决策驾驶舱",
        "把持仓和 3-4 个候选行业放在一起，看对冲度、担保比影响、趋势持续和拐点。这里只做观察纪律，不自动下单。",
        "候选篮子 / 对冲度 / 担保比",
    )
    selected = st.multiselect("候选行业", sectors, default=defaults, max_selections=4)
    buy_amount = st.number_input("计划新增融资买入(万元)", value=200.0)
    acct = {**acct, "basket_buy_amount": buy_amount}
    if st.button("保存候选篮子"):
        basket.save_basket(selected)
        st.success("已保存候选篮子。")

    corr = _corr_for_selected(selected)
    result = basket.evaluate_basket(selected, panel, corr, acct)
    _render_verdict(result)
    _render_items(result)
    _render_ai(panel, result, acct)


def _render_verdict(result: dict) -> None:
    metric_grid(
        [
            ("对冲度", f"{float(result['hedge_score']):.0%}"),
            (
                "加仓后担保比",
                "-" if result["guarantee_after"] is None else f"{result['guarantee_after']:.1%}",
            ),
            ("候选数量", str(len(result["per_item"]))),
        ]
    )
    verdict = str(result["verdict"])
    if "红色" in verdict:
        st.error(verdict)
    elif "黄色" in verdict:
        st.warning(verdict)
    elif "灰色" in verdict:
        st.info(verdict)
    else:
        st.success(verdict)


def _render_items(result: dict) -> None:
    st.subheader("逐项状态")
    table = pd.DataFrame(result["per_item"])
    if table.empty:
        st.info("还没有候选行业。")
        return
    st.dataframe(table, width="stretch", height=260)
    for row in table.to_dict("records"):
        flag = exit_flag(row, max_trend_days=7)
        if flag["exit"]:
            note(f"考虑减仓：{flag['reason']}")


def _render_ai(panel: pd.DataFrame, result: dict, acct: dict) -> None:
    st.subheader("AI 决策简报")
    mainline = panel.iloc[0] if not panel.empty else pd.Series(dtype=object)
    facts = {
        "mainline": str(mainline.get("sector", "")),
        "mainline_trend_days": int(mainline.get("trend_days", 0) or 0),
        "mainline_inflow_10d": round(_yi(mainline.get("inflow_10d", 0)), 2),
        "holdings": acct.get("holdings", []),
        "candidates": [item["sector"] for item in result["per_item"]],
        "hedge_pairs": result["hedge_pairs"],
        "guarantee_ratio": result["guarantee_after"],
    }
    text = advise(facts)
    if "API Key" in text:
        text = _local_advice(facts, result)
    st.write(text)


def _local_advice(facts: dict, result: dict) -> str:
    return (
        f"1. 大趋势：当前主线是 {facts['mainline']}，已持续 {facts['mainline_trend_days']} 天。\n"
        f"2. 资金：10日主力 {facts['mainline_inflow_10d']:+.1f} 亿。\n"
        f"3. 对冲：{result['verdict']}\n"
        f"4. 持仓：只按已录入持仓和候选行业观察，不自动下单。\n"
        f"5. 观察：先等同向扩散，跨负相关行业要减小仓位冲突。"
    )


def _corr_for_selected(selected: list[str]) -> pd.DataFrame:
    if len(selected) < 2:
        return pd.DataFrame()
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=45)).strftime("%Y%m%d")
    series = {}
    for sector in selected:
        try:
            hist = em_client.industry_hist(sector, start, end)
        except Exception:
            hist = pd.DataFrame()
        if not hist.empty and "pct_chg" in hist.columns:
            series[sector] = pd.to_numeric(hist["pct_chg"], errors="coerce").tail(20).reset_index(drop=True)
    return pd.DataFrame(series).corr() if series else pd.DataFrame()


def _yi(value) -> float:
    if pd.isna(value):
        return 0.0
    return float(value) / 100_000_000


if __name__ == "__main__":
    render_page()
