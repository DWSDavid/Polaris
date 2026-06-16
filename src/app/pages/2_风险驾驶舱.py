from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from src.ai.summarize import summarize_sector
from src.app.ui import apply_theme, hero, metric_grid, note, page_intro, section, status_line
from src.compute import risk_engine as rk
from src.compute.exit_signal import exit_flag
from src.compute.portfolio_exposure import (
    build_portfolio_exposure,
    match_sector_name,
    portfolio_offset_report,
    resolve_holding_sector,
)
from src.data import account, em_client
from src.pipeline.sector_panel_v2 import build_sector_panel_v2


DEFAULT_HOLDING = {
    "code": "601688",
    "name": "华泰证券",
    "sector": "证券",
    "shares": 159.21,
    "cost": 19.7,
}


@st.cache_data(ttl=600)
def get_v2_sector_panel() -> pd.DataFrame:
    realtime = em_client.industry_realtime()
    flow_5d = em_client.industry_fund_flow("5日")
    flow_10d = em_client.industry_fund_flow("10日")
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=45)).strftime("%Y%m%d")
    histories = {}
    for sector in realtime.head(20)["sector"].dropna().astype(str):
        try:
            histories[sector] = em_client.industry_hist(sector, start, end)
        except Exception:
            histories[sector] = pd.DataFrame()
    return build_sector_panel_v2(
        industry_realtime=realtime,
        flow_5d=flow_5d,
        flow_10d=flow_10d,
        histories=histories,
    )


def render_page() -> None:
    st.set_page_config(page_title="Polaris 风险驾驶舱", layout="wide")
    apply_theme()
    page_intro(
        "这页回答：当前持仓和融资担保比承受多大回撤压力。",
        "怎么用：录入华泰证券或你的实际持仓后，先看担保比情景，再看行业暴露和拐点提示，避免用加仓放大风险。",
    )

    acct = account.load()
    holding = {**DEFAULT_HOLDING, **(acct.get("holdings", [{}])[0] if acct.get("holdings") else {})}
    mapped_sector = resolve_holding_sector(holding, fallback=str(holding.get("sector") or "证券"))

    try:
        sector_panel = get_v2_sector_panel()
        load_error = None
    except Exception as exc:
        sector_panel = pd.DataFrame()
        load_error = exc

    if sector_panel.empty:
        status_line("东财 v2 行业面板暂不可用，风险驾驶舱只显示本地担保比。")
        if load_error:
            st.error(f"东财接口异常：{load_error}")

    sectors = sector_panel["sector"].dropna().astype(str).tolist() if not sector_panel.empty else [mapped_sector]
    matched_sector = match_sector_name(mapped_sector, sectors)
    sector_default = _index_or_zero(sectors, matched_sector or mapped_sector)

    with st.form("account"):
        col1, col2, col3 = st.columns(3)
        total = col1.number_input(
            "总资产(万元)", value=_value(acct, "total_assets", 3143.0)
        )
        debt = col2.number_input("融资负债(万元)", value=_value(acct, "debt", 1860.0))
        cash = col3.number_input("现金(万元)", value=float(acct.get("cash", 0.0)))
        rate = col1.number_input(
            "年利率",
            value=float(acct.get("annual_rate", 0.035)),
            format="%.3f",
        )
        warning_line = col2.number_input(
            "警戒线",
            value=float(acct.get("warning_line", 1.50)),
        )
        liquidation_line = col3.number_input(
            "平仓线",
            value=float(acct.get("liquidation_line", 1.30)),
        )
        code = col1.text_input("持仓代码", value=str(holding.get("code", "601688")))
        name = col2.text_input("持仓名称", value=str(holding.get("name", "华泰证券")))
        selected_sector = col3.selectbox("所属行业", sectors, index=sector_default)
        shares = col1.number_input(
            "股数(万股)",
            value=float(holding.get("shares", DEFAULT_HOLDING["shares"])),
        )
        price = col2.number_input(
            "现价(元)",
            value=float(holding.get("price") or holding.get("cost") or DEFAULT_HOLDING["cost"]),
        )
        saved = st.form_submit_button("保存并计算")

    current_holding = {
        "code": code,
        "name": name,
        "sector": match_sector_name(
            resolve_holding_sector({"code": code}, fallback=selected_sector),
            sectors,
        ),
        "shares": shares,
        "cost": price,
        "price": price,
    }
    if saved:
        account.save(
            {
                **acct,
                "total_assets": total,
                "debt": debt,
                "cash": cash,
                "annual_rate": rate,
                "warning_line": warning_line,
                "liquidation_line": liquidation_line,
                "holdings": [current_holding],
            }
        )

    hero(
        "风险驾驶舱",
        "把融资担保比、持仓行业状态、主力资金和对冲风险放在同一屏。这里只做风险解释，不给自动交易指令。",
        "v2 东财行业面板 / 本地账户",
    )

    if debt <= 0 or shares <= 0:
        st.warning("融资负债和股数需要大于 0 才能计算风险。")
        return

    ratio = rk.guarantee_ratio(total, debt)
    metric_grid(
        [
            ("当前担保比", f"{ratio * 100:.1f}%"),
            ("距警戒线", f"{(ratio - warning_line) * 100:.1f}pp"),
            ("距平仓线", f"{(ratio - liquidation_line) * 100:.1f}pp"),
            ("强平价", f"{rk.liquidation_price(shares, cash, debt, liquidation_line):.2f} 元"),
        ]
    )
    if ratio < warning_line:
        note("担保比低于警戒线，优先看现金、仓位和行业拐点，别让补仓变成扩大风险。")

    scenario_tab, exposure_tab, ai_tab = st.tabs(["担保比情景", "行业暴露", "AI 解释"])
    with scenario_tab:
        _render_margin_scenarios(price, shares, cash, debt, rate)
    with exposure_tab:
        _render_exposure(current_holding, sector_panel)
    with ai_tab:
        _render_ai_summary(current_holding, sector_panel, ratio)


def _render_margin_scenarios(
    price: float,
    shares: float,
    cash: float,
    debt: float,
    rate: float,
) -> None:
    section("回撤情景", "先看担保比在不同回撤下的压力，再决定是否动仓位。")
    scenarios = pd.DataFrame(
        rk.drawdown_scenarios(price, shares, cash, debt, [0.05, 0.10, 0.20])
    )
    st.dataframe(scenarios, width="stretch")
    buy = st.number_input("拟融资买入(万元)", value=200.0)
    st.write(f"加仓后担保比: {rk.guarantee_ratio_after_buy(cash + shares * price, debt, buy) * 100:.1f}%")
    carry = rk.interest_carry(debt, rate)
    st.caption(
        f"利息拖累: {carry['per_year']:.1f} 万元/年，约 {carry['per_month']:.2f} 万元/月"
    )


def _render_exposure(holding: dict, sector_panel: pd.DataFrame) -> None:
    section("组合对冲暴露", "避免金融和科技互相抵消，让方向判断真正反映到收益。")
    diagnostics = _diagnostics_from_v2_panel(sector_panel)
    stock_panel = _stock_panel_from_holdings([holding])
    exposure = build_portfolio_exposure([holding], stock_panel, diagnostics)
    offset = portfolio_offset_report(exposure)

    if offset["offset_level"] == "high":
        st.error(offset["message"])
    elif offset["offset_level"] == "medium":
        st.warning(offset["message"])
    else:
        st.info(offset["message"])

    if exposure.empty:
        st.info("当前持仓没有匹配到行业暴露：东财未接入或行业名未匹配。")
        return

    st.dataframe(
        exposure.rename(
            columns={
                "sector": "行业",
                "market_value_wan": "市值(万元)",
                "weight": "持仓权重",
                "fund_flow_yi": "板块资金(亿)",
                "money_direction": "资金方向",
                "trend_label": "1-3周趋势",
                "split_label": "分化/拐点",
            }
        ),
        width="stretch",
        column_config={
            "市值(万元)": st.column_config.NumberColumn(format="%.1f"),
            "持仓权重": st.column_config.ProgressColumn(
                min_value=0,
                max_value=1,
                format="%.0f%%",
            ),
            "板块资金(亿)": st.column_config.NumberColumn(format="%+.1f"),
        },
    )


def _render_ai_summary(holding: dict, sector_panel: pd.DataFrame, ratio: float) -> None:
    row = _sector_row(sector_panel, str(holding.get("sector", "")))
    if sector_panel.empty:
        st.info("AI 解释缺少行业行：东财行业面板暂不可用。")
    elif row.empty:
        st.info(f"AI 解释缺少行业行：{holding.get('sector')} 未匹配到东财行业名。")
    facts = {
        "sector": str(holding.get("sector", "")),
        "state": str(row.get("state", "未知")),
        "trend_days": int(row.get("trend_days", 0) or 0),
        "pct_chg": round(float(row.get("pct_chg", 0) or 0), 2),
        "main_net_inflow": round(_yi(row.get("main_net_inflow", 0)), 2),
        "inflow_5d": round(_yi(row.get("inflow_5d", 0)), 2),
        "inflow_10d": round(_yi(row.get("inflow_10d", 0)), 2),
        "diffusion": round(float(row.get("diffusion", 0) or 0), 2),
        "turning_point": bool(row.get("turning_point", False)),
        "top_leaders": str(row.get("top_leaders", "")),
        "holding": f"{holding.get('name')}({holding.get('code')})",
        "guarantee_ratio": round(ratio, 3),
    }
    st.dataframe(pd.DataFrame([facts]), width="stretch", height=120)
    flag = exit_flag(row, max_trend_days=7)
    if flag["exit"]:
        note(f"考虑减仓：{flag['reason']}")
    try:
        text = summarize_sector(facts)
    except Exception as exc:
        text = f"AI 暂不可用：{exc}。本页仍只展示系统计算出的真实数值。"
    if "API Key" in text:
        text = (
            f"{facts['holding']} 属于 {facts['sector']}，行业状态 {facts['state']}，"
            f"趋势持续 {facts['trend_days']} 天，10日主力 {facts['inflow_10d']:+.1f} 亿，"
            f"担保比 {facts['guarantee_ratio']:.1%}。先看行业是否继续扩散，再决定是否加减仓。"
        )
    st.write(text)


def _diagnostics_from_v2_panel(panel: pd.DataFrame) -> pd.DataFrame:
    if panel.empty:
        return pd.DataFrame(
            columns=[
                "sector",
                "fund_flow_yi",
                "money_direction",
                "trend_label",
                "split_label",
            ]
        )
    out = panel.copy()
    out["fund_flow_yi"] = (
        pd.to_numeric(out.get("main_net_inflow"), errors="coerce").fillna(0)
        + pd.to_numeric(out.get("inflow_10d"), errors="coerce").fillna(0)
    ) / 100_000_000
    out["money_direction"] = out["fund_flow_yi"].map(
        lambda value: "净流入" if value > 0 else ("净流出" if value < 0 else "中性")
    )
    out["trend_label"] = out.apply(
        lambda row: f"{row.get('state', '未知')} / {int(row.get('trend_days', 0) or 0)}天",
        axis=1,
    )
    out["split_label"] = out.apply(
        lambda row: "拐点预警" if bool(row.get("turning_point", False)) else str(row.get("state", "未知")),
        axis=1,
    )
    return out[
        ["sector", "fund_flow_yi", "money_direction", "trend_label", "split_label"]
    ]


def _stock_panel_from_holdings(holdings: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "code": str(item.get("code", "")).zfill(6),
                "name": item.get("name", ""),
                "sector": item.get("sector", "未知"),
            }
            for item in holdings
        ]
    )


def _sector_row(panel: pd.DataFrame, sector: str) -> pd.Series:
    if panel.empty:
        return pd.Series(dtype=object)
    matched = panel.loc[panel["sector"] == sector]
    if matched.empty:
        return pd.Series(dtype=object)
    return matched.iloc[0]


def _value(acct: dict, key: str, fallback: float) -> float:
    value = acct.get(key, fallback)
    return fallback if value in (None, 0, 0.0) else float(value)


def _index_or_zero(values: list[str], target: str) -> int:
    return values.index(target) if target in values else 0


def _yi(value) -> float:
    if pd.isna(value):
        return 0.0
    return float(value) / 100_000_000


if __name__ == "__main__":
    render_page()
