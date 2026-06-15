import pandas as pd
import streamlit as st

from src.app.ui import apply_theme
from src.compute.market_intelligence import sector_diagnostics
from src.compute.portfolio_exposure import (
    build_portfolio_exposure,
    portfolio_offset_report,
)
from src.compute import risk_engine as rk
from src.data import account
from src.pipeline.refresh import refresh_eod, stock_panel


def _value(acct: dict, key: str, fallback: float) -> float:
    value = acct.get(key, fallback)
    return fallback if value in (None, 0, 0.0) else float(value)


st.set_page_config(page_title="风险驾驶舱", layout="wide")
apply_theme()
st.title("风险驾驶舱")

acct = account.load()
holding = acct["holdings"][0] if acct.get("holdings") else {}

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
    shares = col2.number_input(
        "股数(万股)",
        value=float(holding.get("shares", 159.21)),
    )
    price = col3.number_input("现价(元)", value=float(holding.get("cost", 19.7)))
    saved = st.form_submit_button("保存并计算")

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
            "holdings": [
                {"code": code, "name": "持仓", "shares": shares, "cost": price}
            ],
        }
    )

if debt <= 0 or shares <= 0:
    st.warning("融资负债和股数需要大于 0 才能计算风险。")
    st.stop()

ratio = rk.guarantee_ratio(total, debt)
col1, col2 = st.columns(2)
col1.metric(
    "当前担保比",
    f"{ratio * 100:.1f}%",
    delta=f"距平仓线 {(ratio - liquidation_line) * 100:.1f}pp",
)
col2.metric(
    "强平价",
    f"{rk.liquidation_price(shares, cash, debt, liquidation_line):.2f} 元",
)

st.subheader("回撤情景")
scenarios = pd.DataFrame(
    rk.drawdown_scenarios(price, shares, cash, debt, [0.05, 0.10, 0.20])
)
st.dataframe(scenarios, width="stretch")

st.subheader("加仓影响")
buy = st.number_input("拟融资买入(万元)", value=200.0)
st.write(f"加仓后担保比: {rk.guarantee_ratio_after_buy(total, debt, buy) * 100:.1f}%")

carry = rk.interest_carry(debt, rate)
st.caption(
    f"利息拖累: {carry['per_year']:.1f} 万元/年，约 {carry['per_month']:.2f} 万元/月"
)

st.subheader("组合对冲暴露")
sector_panel = refresh_eod()
stocks = stock_panel()
diagnostics = sector_diagnostics(sector_panel, stocks)
exposure = build_portfolio_exposure(acct.get("holdings", []), stocks, diagnostics)
offset = portfolio_offset_report(exposure)

if offset["offset_level"] == "high":
    st.error(offset["message"])
elif offset["offset_level"] == "medium":
    st.warning(offset["message"])
else:
    st.info(offset["message"])

if not exposure.empty:
    exposure_view = exposure.rename(
        columns={
            "sector": "板块",
            "market_value_wan": "市值(万元)",
            "weight": "持仓权重",
            "fund_flow_yi": "板块资金(亿)",
            "money_direction": "资金方向",
            "trend_label": "1-3周趋势",
            "split_label": "分化",
        }
    )
    st.dataframe(
        exposure_view,
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
